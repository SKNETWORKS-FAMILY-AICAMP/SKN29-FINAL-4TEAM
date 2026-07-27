#!/usr/bin/env python3
"""Compatibility wrapper for synthetic data generation."""

import sys

from watercare.cli import legacy_main


if __name__ == "__main__":
    raise SystemExit(legacy_main("step4", sys.argv[1:]))
