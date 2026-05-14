"""Stears Elections loader — STUB pending Phase C.

Stears data is proprietary; reach out for permission before ingesting.
Until then, fall back to `generic_csv.load_csv()` after manual export.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def load_stears(*args, **kwargs):  # type: ignore[no-untyped-def]
    raise NotImplementedError(
        "Stears loader is a Phase C stub. Use generic_csv.load_csv() after "
        "manually exporting CSV; ensure licensing is cleared."
    )
