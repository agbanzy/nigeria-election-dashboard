"""OCR pipeline for INEC EC8A polling-unit result sheets.

Ports the core image-preprocessing + tesseract + regex-parsing pieces from
the legacy `election_dashboard.py` (lines ~500-820) into the new package.

Public API:

    from app.ocr.ec8a import parse_ec8a_image, ParsedEC8A

    bytes_ = open("ec8a.jpg", "rb").read()
    parsed = parse_ec8a_image(bytes_, cycle=2023)
    if parsed:
        print(parsed.party_votes, parsed.total_valid_votes)

If pytesseract/Pillow aren't installed (or tesseract binary missing) the
function returns None — callers handle that as "OCR unavailable, skip".

Phase-D / future-work: confidence scoring, supplementary form variants,
multi-language hints, persisting raw OCR text into irev_raw_cache for
re-parsing without re-OCR.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass

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


# Known party codes — used to anchor the regex parser. Extend as new parties
# appear in cycles we're ingesting.
KNOWN_PARTIES: tuple[str, ...] = (
    "APC", "PDP", "LP", "NNPP", "APGA", "ADC", "YPP", "ADP", "SDP",
    "AAC", "AA", "ANRP", "BP", "PRP", "ZLP", "APM", "NRM", "PPA",
    "CPC", "ACN", "ANPP", "AD",
)


def parse_ec8a_image(image_bytes: bytes, *, cycle: int | None = None) -> ParsedEC8A | None:
    """Parse a single EC8A scan. Returns None if OCR is unavailable.

    Pipeline (mirrors the legacy implementation):
      1. Open image via PIL.
      2. Apply preprocessing variants (greyscale + contrast boost; on-the-fly
         deskew is skipped because INEC scans are usually already aligned).
      3. tesseract_to_string with the "eng" model.
      4. Regex over the resulting text to pull header counts + party votes.

    Robustness: the parser is permissive — it accepts any party code in
    KNOWN_PARTIES even if the OCR slightly mangles surrounding text. Counts
    that can't be parsed remain None instead of raising.
    """
    try:
        import pytesseract
        from PIL import Image, ImageEnhance, ImageOps
    except ImportError:
        log.info("OCR deps unavailable; returning None")
        return None

    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception:
        log.exception("OCR: failed to open image")
        return None

    # Pre-processing: convert to grayscale + bump contrast.
    proc = ImageOps.grayscale(img)
    proc = ImageEnhance.Contrast(proc).enhance(1.6)
    proc = ImageEnhance.Sharpness(proc).enhance(1.2)

    try:
        text = pytesseract.image_to_string(proc, lang="eng")
    except Exception as exc:
        log.warning("OCR: tesseract failure: %s", exc)
        return None

    if not text:
        return None

    return _parse_text(text, cycle=cycle)


def _parse_text(text: str, *, cycle: int | None) -> ParsedEC8A:
    """Pure-function regex parser — testable without tesseract."""
    normalized = text.replace(",", "").replace(".", " ")

    party_votes: dict[str, int] = {}
    for code in KNOWN_PARTIES:
        # Look for "<CODE> <number>" or "<CODE>:<number>" on the line.
        # Allow up to 3 chars of OCR noise between code and number.
        for m in re.finditer(
            rf"\b{re.escape(code)}\b[^\d]{{0,6}}(\d{{1,7}})", normalized, flags=re.IGNORECASE
        ):
            v = int(m.group(1))
            # Sanity ceiling: no polling unit has more than ~5000 voters
            if v > 100_000:
                continue
            party_votes[code] = max(party_votes.get(code, 0), v)
            break

    registered = _first_int_after(normalized, ("registered", "registered voters"))
    accredited = _first_int_after(normalized, ("accredited", "accredited voters"))
    valid = _first_int_after(normalized, ("valid votes", "total valid"))
    rejected = _first_int_after(normalized, ("rejected", "rejected votes"))

    # Confidence: rough heuristic — % of the four header counts we found.
    found = sum(1 for x in (registered, accredited, valid, rejected) if x is not None)
    confidence = found / 4.0

    return ParsedEC8A(
        registered_voters=registered,
        accredited_voters=accredited,
        total_valid_votes=valid,
        total_rejected_votes=rejected,
        party_votes=party_votes,
        confidence=confidence,
        raw_text=text,
    )


def _first_int_after(text: str, anchors: tuple[str, ...]) -> int | None:
    for anchor in anchors:
        m = re.search(rf"{anchor}\s*[:\-]?\s*(\d{{1,6}})", text, flags=re.IGNORECASE)
        if m:
            v = int(m.group(1))
            if 0 <= v <= 100_000:
                return v
    return None
