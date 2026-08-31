"""Opt-in Windows Docker Desktop probe using tiny, uniquely owned OCI images.

No registry access, containers, or volumes are created. The only removal targets
are images made by this invocation, verified by ID and a unique ownership label.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "image_maintenance", ROOT / "scripts/deployment/production/maintain_release_images.py",
)
assert SPEC is not None and SPEC.loader is not None
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)
LABEL = "waterbridge.qa.image-retention-probe"
REPO = "111111111111.dkr.ecr.ap-northeast-2.amazonaws.com/waterbridge/ai"


def image_archive(path: Path, owner: str) -> list[str]:
    blobs = {}

    def blob(value, media_type):
        content = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        checksum = hashlib.sha256(content).hexdigest()
        blobs["blobs/sha256/" + checksum] = content
        return {"mediaType": media_type, "digest": "sha256:" + checksum, "size": len(content)}

    manifests, references = [], []
    for role in ("obsolete", "retained"):
        config = blob({
            "architecture": "amd64", "os": "linux",
            "config": {"Labels": {LABEL: owner, "waterbridge.qa.role": role}},
            "rootfs": {"type": "layers", "diff_ids": []}, "history": [],
        }, "application/vnd.oci.image.config.v1+json")
        descriptor = blob({
            "schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "config": config, "layers": [],
        }, "application/vnd.oci.image.manifest.v1+json")
        reference = REPO + "@" + descriptor["digest"]
        descriptor["annotations"] = {
            "io.containerd.image.name": reference,
            "org.opencontainers.image.ref.name": reference,
        }
        manifests.append(descriptor)
        references.append(reference)
    blobs["oci-layout"] = b'{"imageLayoutVersion":"1.0.0"}'
    blobs["index.json"] = json.dumps({"schemaVersion": 2, "manifests": manifests}).encode()
    with tarfile.open(path, "w") as archive:
        for name, content in blobs.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            archive.addfile(entry, io.BytesIO(content))
    return references


def run_probe() -> None:
    endpoint = POLICY.docker("context", "inspect", "--format", "{{.Endpoints.docker.Host}}")
    if not endpoint.startswith("npipe://"):
        raise RuntimeError("This probe is restricted to local Windows Docker Desktop")
    if POLICY.docker("info", "--format", "{{.Driver}}") != "overlayfs":
        raise RuntimeError("The containerd image store is required")
    before = set(POLICY.docker("image", "ls", "--quiet", "--no-trunc").split())
    volumes = POLICY.docker("volume", "ls", "--quiet")
    owner = str(uuid.uuid4())
    with tempfile.TemporaryDirectory(prefix="waterbridge-image-probe-") as temporary:
        archive = Path(temporary) / "owned-images.tar"
        references = image_archive(archive, owner)
        try:
            POLICY.docker("image", "load", "--input", str(archive))
            obsolete, retained = [POLICY.image_metadata(ref) for ref in references]
            for image, reference in zip((obsolete, retained), references):
                if image[0] in before or reference not in image[1] & image[2]:
                    raise RuntimeError("Did not reproduce uniquely owned containerd digest aliases")
                label = POLICY.docker("image", "inspect", "--format", '{{index .Config.Labels "' + LABEL + '"}}', image[0])
                if label != owner:
                    raise RuntimeError("Image ownership mismatch")
            known, protected = set(references), {references[1]}
            if not POLICY.eligible(obsolete, known, protected, {retained[0]}):
                raise RuntimeError("Obsolete image was not selected")
            if POLICY.eligible(retained, known, protected, {retained[0]}):
                raise RuntimeError("Retained image was incorrectly selected")
            POLICY.docker("image", "rm", "--no-prune", obsolete[0])
            after = set(POLICY.docker("image", "ls", "--quiet", "--no-trunc").split())
            if obsolete[0] in after or POLICY.image_metadata(references[1])[0] != retained[0]:
                raise RuntimeError("Deletion or retained-image check failed")
            if not before <= after or POLICY.docker("volume", "ls", "--quiet") != volumes:
                raise RuntimeError("Unrelated images or volumes changed during the probe")
            print("DOCKER_RETENTION_PROBE_PASS obsolete_removed=1 retained_preserved=1 volumes_unchanged=true")
        finally:
            for reference in references:
                try:
                    identifier = POLICY.image_metadata(reference)[0]
                except POLICY.MaintenanceError:
                    continue
                label = POLICY.docker("image", "inspect", "--format", '{{index .Config.Labels "' + LABEL + '"}}', identifier)
                if identifier in before or label != owner:
                    raise RuntimeError("Refusing cleanup of a non-owned image")
                POLICY.docker("image", "rm", "--no-prune", identifier)
            print("DOCKER_RETENTION_PROBE_CLEANUP_PASS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-local-probe", action="store_true", required=True)
    parser.parse_args()
    run_probe()
