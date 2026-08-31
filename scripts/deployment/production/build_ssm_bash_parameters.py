"""Encode explicit Bash execution for AWS-RunShellScript's outer POSIX shell.

Runs on the GitHub runner, not the EC2 host. No AWS calls or file writes.
Each argument is an already constructed trusted shell command; this helper
quotes the entire Bash body for the outer sh, preserving inner Bash %q quoting.
"""

from __future__ import annotations

import argparse
import json
import shlex


def build_parameters(commands: list[str]) -> dict[str, list[str]]:
    if not commands or any(
        not isinstance(command, str) or not command.strip() or "\x00" in command
        for command in commands
    ):
        raise ValueError("SSM commands must be non-empty strings without NUL")
    body = "\n".join(commands)
    return {"commands": ["exec /bin/bash -euo pipefail -c " + shlex.quote(body)]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("commands", nargs="+")
    args = parser.parse_args()
    try:
        parameters = build_parameters(args.commands)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(parameters))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
