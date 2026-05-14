"""INEC archived PDF loader — STUB pending Phase D.

INEC's 2015 + 2019 result PDFs at LGA level. Uses `ocr/ec8a.py` for parsing.
Output is fed into `generic_csv.load_csv()` shape.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def load_inec_pdf(*args, **kwargs):  # type: ignore[no-untyped-def]
    raise NotImplementedError("INEC PDF loader is a Phase D stub (OCR pipeline).")
