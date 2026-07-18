"""Build the Alembic config programmatically.

The migration directory ships inside the package, so ``emctl migrate`` works
whether run from a checkout or an installed wheel. ``env.py`` reads
``DATABASE_URL`` from the environment; no URL lives in ``alembic.ini``.
"""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config

import emctl


def make_config() -> Config:
    package_dir = Path(emctl.__file__).resolve().parent
    cfg = Config()
    cfg.set_main_option("script_location", str(package_dir / "migrations"))
    return cfg
