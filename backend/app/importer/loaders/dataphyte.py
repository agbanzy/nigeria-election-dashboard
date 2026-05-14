"""Dataphyte / Nubia loader — STUB pending Phase C.

Dataphyte publishes open NASS data for 2019 + 2023 at state level. Format is
CSV; map columns to ResultRow fields and use generic_csv.load_csv().
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def load_dataphyte(*args, **kwargs):  # type: ignore[no-untyped-def]
    raise NotImplementedError("Dataphyte loader is a Phase C stub.")
