#!/usr/bin/env python3
"""Compatibility wrapper for retention inventory."""

import sys

from watercare.cli import legacy_main


if __name__ == "__main__":
    raise SystemExit(legacy_main("step6_inventory", sys.argv[1:]))
