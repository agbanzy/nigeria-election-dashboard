"""Shared Flask-Limiter instance.

Targeted per-IP limits on the abuse-sensitive endpoints (login brute-force,
developer-key spam) rather than a blanket global limit — a global per-IP cap
would throttle legitimate dashboard users sharing carrier-grade NAT, which is
common in Nigeria. Volumetric/DoS protection belongs at the edge (Cloudflare),
not here; this layer stops credential brute force and application spam.

Storage defaults to in-process memory (per-worker buckets — weak but real).
Set RATELIMIT_STORAGE_URI to a redis:// URL to share buckets across workers.
"""

from __future__ import annotations

import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
    default_limits=[],  # no global cap — see module docstring (CGNAT)
    headers_enabled=True,
)
