#!/usr/bin/env python3
"""Compatibility wrapper for processed data validation."""

import sys

from watercare.cli import legacy_main


if __name__ == "__main__":
    raise SystemExit(legacy_main("step2", sys.argv[1:]))
