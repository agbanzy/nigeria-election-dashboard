"""OCR pipeline for INEC EC8A result-sheet scans.

Phase A: thin facade. The real preprocessing + tesseract + regex parsing logic
lives in legacy `election_dashboard.py` (lines ~500-820) and will be migrated
verbatim in Phase D when we ingest 2015 + 2019 PDFs.

For now this module exposes the public surface so importer loaders can import
without depending on the legacy file.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedEC8A:
    registered_voters: int | None
    accredited_voters: int | None
    total_valid_votes: int | None
    total_rejected_votes: int | None
    party_votes: dict[str, int]
    confidence: float
    raw_text: str


def parse_ec8a_image(image_bytes: bytes, *, cycle: int | None = None) -> ParsedEC8A | None:
    """Parse a single EC8A scan. Returns None when OCR is unavailable.

    Phase D will port the full preprocessing + tesseract pipeline from
    `election_dashboard.py`. Until then, callers must handle a None result.
    """
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        log.info("OCR dependencies not installed — returning None")
        return None

    log.warning("EC8A parser not yet ported from legacy monolith (Phase D)")
    return None
