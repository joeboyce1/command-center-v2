#!/usr/bin/env python3
"""Convenience entry point: python run_study.py [--synthetic] [...]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from nfl_seasonality.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
