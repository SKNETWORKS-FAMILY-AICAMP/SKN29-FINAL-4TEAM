#!/usr/bin/env python3
"""WaterCare declarative pipeline entry point.

Stage 3 exposes equivalence validation only. Build/QA compatibility commands
are enabled when legacy wrappers are switched in stage 4.
"""

from watercare.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
