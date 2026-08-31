"""Bound local release image retention; never prune containers, volumes or caches.

The deployment shell owns deploy.lock on inherited fd 9. Only non-secret
release manifests and explicitly selected Docker metadata fields are read.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path("/opt/waterbridge")
MIN_FREE_BYTES = 10 * 1024**3
SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
REPOSITORY = re.compile(
    r"[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/waterbridge/(web|backend|ai)"
)
IMAGE_FORMAT = '[{{json .Id}},{{json .RepoTags}},{{json .RepoDigests}}]'
SERVICES = ("WEB", "BACKEND", "AI")


class MaintenanceError(RuntimeError):
    """Reason codes only: never forward subprocess output or environment data."""


def docker(*args: str) -> str:
    try:
        result = subprocess.run(
            ["docker", *args], capture_output=True, text=True,
            check=False, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MaintenanceError("DOCKER_UNAVAILABLE") from exc
    if result.returncode:
        raise MaintenanceError("DOCKER_COMMAND_FAILED")
    return result.stdout.strip()


def manifest(payload: Path, base: Path) -> set[str]:
    """Do not source release.env or resolve Compose's protected env_file entries."""
    resolved = payload.resolve(strict=True)
    if (
        resolved != payload.absolute()
        or resolved.name != "payload"
        or not SHA.fullmatch(resolved.parent.name)
        or resolved.parent.parent != base / "releases"
    ):
        raise MaintenanceError("RELEASE_PATH_INVALID")
    path = resolved / "release.env"
    if path.is_symlink() or not path.is_file():
        raise MaintenanceError("RELEASE_MANIFEST_UNAVAILABLE")
    keys = {f"{service}_{suffix}" for service in SERVICES for suffix in ("IMAGE", "IMAGE_DIGEST")}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if key in keys and separator:
            if key in values:
                raise MaintenanceError("RELEASE_IMAGE_DUPLICATED")
            values[key] = value
    refs = set()
    registries = set()
    for service in SERVICES:
        repository = values.get(f"{service}_IMAGE", "")
        digest = values.get(f"{service}_IMAGE_DIGEST", "")
        match = REPOSITORY.fullmatch(repository)
        if not match or match[1] != service.lower() or not DIGEST.fullmatch(digest):
            raise MaintenanceError("RELEASE_IMAGE_INVALID")
        registries.add(repository.split("/", 1)[0])
        refs.add(f"{repository}@{digest}")
    if len(registries) != 1:
        raise MaintenanceError("RELEASE_REGISTRY_MISMATCH")
    return refs


def release_sets(base: Path, incoming: Path) -> tuple[set[str], set[str], set[str]]:
    protected = manifest(incoming, base)
    repositories = {ref.split("@", 1)[0] for ref in protected}
    required = set()
    for name in ("current", "previous"):
        link = base / name
        if link.is_symlink():
            required.update(manifest(link.resolve(strict=True), base))
        elif link.exists():
            raise MaintenanceError("RELEASE_POINTER_INVALID")
    protected.update(required)
    known = set(protected)
    # An invalid historical manifest is NOT evidence of ownership: keep it.
    for release in (base / "releases").iterdir():
        if not SHA.fullmatch(release.name) or release.is_symlink():
            continue
        try:
            known.update(manifest(release / "payload", base))
        except (MaintenanceError, OSError, UnicodeError, RuntimeError):
            continue
    known = {ref for ref in known if ref.split("@", 1)[0] in repositories}
    return protected, required, known


def image_metadata(reference: str) -> tuple[str, set[str], set[str]]:
    try:
        identifier, tags, digests = json.loads(
            docker("image", "inspect", "--format", IMAGE_FORMAT, reference)
        )
        if not isinstance(identifier, str) or not DIGEST.fullmatch(identifier):
            raise ValueError
        tags = [] if tags is None else tags
        digests = [] if digests is None else digests
        if not isinstance(tags, list) or not isinstance(digests, list):
            raise ValueError
        if not all(isinstance(ref, str) for ref in tags + digests):
            raise ValueError
        return identifier, set(tags), set(digests)
    except (ValueError, TypeError) as exc:
        raise MaintenanceError("IMAGE_METADATA_INVALID") from exc


def container_images() -> set[str]:
    identifiers = docker("container", "ls", "--all", "--quiet", "--no-trunc").split()
    images = set()
    for identifier in identifiers:
        image = docker("container", "inspect", "--format", "{{.Image}}", identifier)
        if not DIGEST.fullmatch(image):
            raise MaintenanceError("CONTAINER_IMAGE_INVALID")
        images.add(image)
    return images


def eligible(
    image: tuple[str, set[str], set[str]], known: set[str],
    protected_refs: set[str], protected_ids: set[str],
) -> bool:
    identifier, tags, digests = image
    # Unknown aliases, dangling images, other accounts/repos and mutable tags
    # stay untouched, even when an image also has an owned release reference.
    repositories = {ref.split("@", 1)[0] for ref in known}
    return bool(
        identifier not in protected_ids
        and digests
        and digests <= known
        and not digests.intersection(protected_refs)
        and all(
            tag.rpartition(":")[0] in repositories
            and SHA.fullmatch(tag.rpartition(":")[2])
            for tag in tags
        )
    )


def disk_paths(base: Path) -> list[tuple[str, Path]]:
    root = Path(docker("info", "--format", "{{.DockerRootDir}}"))
    if not root.is_absolute() or not root.is_dir():
        raise MaintenanceError("DOCKER_STORAGE_PATH_INVALID")
    paths = [("host", Path("/")), ("release", base), ("docker", root)]
    # DockerRootDir alone omits the containerd image store on Engine 29+.
    containerd = Path("/var/lib/containerd")
    if containerd.is_dir():
        paths.append(("containerd", containerd))
    elif docker("info", "--format", "{{.Driver}}") == "overlayfs":
        raise MaintenanceError("CONTAINERD_STORAGE_PATH_UNVERIFIED")
    return paths


def check_space(paths: list[tuple[str, Path]], *, enforce: bool) -> None:
    enough = True
    for label, path in paths:
        free = shutil.disk_usage(path).free
        print(f"DEPLOYMENT_DISK_SPACE store={label} free_bytes={free} required_bytes={MIN_FREE_BYTES}")
        enough = enough and free >= MIN_FREE_BYTES
    if enforce and not enough:
        raise MaintenanceError("INSUFFICIENT_DISK_SPACE")


def maintain(base: Path, incoming: Path, *, apply: bool, before_pull: bool) -> None:
    if (base / "shared/ai-handoff-canary.state").exists():
        raise MaintenanceError("CANARY_ACTIVE")
    protected_refs, required_refs, known = release_sets(base, incoming)
    protected_ids = container_images()
    identifiers = set(docker("image", "ls", "--quiet", "--no-trunc").split())
    inventory = [image_metadata(identifier) for identifier in sorted(identifiers)]
    local_refs = set().union(*(image[2] for image in inventory))
    # Current/previous images must actually be available before any removal.
    for reference in sorted(required_refs | (protected_refs & local_refs)):
        protected_ids.add(image_metadata(reference)[0])
    paths = disk_paths(base)
    check_space(paths, enforce=False)
    candidates = [image for image in inventory if eligible(image, known, protected_refs, protected_ids)]
    print(f"RELEASE_IMAGE_CLEANUP_PLAN candidates={len(candidates)} apply={str(apply).lower()}")
    removed = failures = 0
    if apply:
        for image in candidates:
            identifier = image[0]
            # Recheck aliases and container references immediately before removal.
            current = image_metadata(identifier)
            if current != image or not eligible(
                current, known, protected_refs, protected_ids | container_images(),
            ):
                continue
            try:
                # No force: Docker may refuse multi-alias/in-use images. No parent
                # pruning: only this explicitly proven release image is targeted.
                docker("image", "rm", "--no-prune", identifier)
                removed += 1
            except MaintenanceError:
                failures += 1
                print(f"RELEASE_IMAGE_CLEANUP_WARNING image={identifier} reason=REMOVE_REFUSED")
    print(f"RELEASE_IMAGE_CLEANUP_RESULT removed={removed} refused={failures} volumes_touched=false")
    check_space(paths, enforce=before_pull)


def require_deployment_lock(base: Path) -> None:
    import fcntl  # Host-only; pure policy tests also run on Windows.

    try:
        inherited = os.fstat(9)
        expected = (base / "shared/deploy.lock").stat()
        if (inherited.st_dev, inherited.st_ino) != (expected.st_dev, expected.st_ino):
            raise MaintenanceError("DEPLOYMENT_LOCK_INVALID")
        fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        raise MaintenanceError("DEPLOYMENT_LOCK_REQUIRED") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--phase", choices=("before-pull", "after-success"), required=True)
    parser.add_argument("--apply", action="store_true", help="Remove proven obsolete release images")
    args = parser.parse_args()
    try:
        require_deployment_lock(BASE_DIR)
        maintain(BASE_DIR, args.release_dir, apply=args.apply, before_pull=args.phase == "before-pull")
    except (MaintenanceError, OSError, UnicodeError, RuntimeError) as exc:
        reason = str(exc) if isinstance(exc, MaintenanceError) else type(exc).__name__
        print(f"RELEASE_IMAGE_MAINTENANCE_FAILED reason={reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
