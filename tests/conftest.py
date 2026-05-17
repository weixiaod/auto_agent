"""Shared pytest configuration.

Adds the repo root to sys.path so `import tools.xxx` works without installing.
Keep this file minimal — skill-specific fixtures belong in per-skill conftests.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
