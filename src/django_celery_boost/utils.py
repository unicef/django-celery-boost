from __future__ import annotations

import warnings
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from django.conf import settings

if TYPE_CHECKING:
    from django.http import HttpRequest

DEFAULT_FLOWER_ADDRESS = "/flower"


class CeleryBoostDeprecationWarning(DeprecationWarning):
    pass


def resolve_flower_setting() -> str:
    """Return the configured Flower base URL.

    Precedence:

    1. ``CELERY_BOOST_FLOWER`` (canonical)
    2. ``CELERY_FLOW_ADDRESS`` (deprecated alias)
    3. ``"/flower"``
    """
    value = getattr(settings, "CELERY_BOOST_FLOWER", None)
    if value:
        return value
    legacy = getattr(settings, "CELERY_FLOW_ADDRESS", None)
    if legacy:
        warnings.warn(
            "CELERY_FLOW_ADDRESS is deprecated, use CELERY_BOOST_FLOWER instead.",
            CeleryBoostDeprecationWarning,
            stacklevel=2,
        )
        return legacy
    return DEFAULT_FLOWER_ADDRESS


def get_flower_address(request: HttpRequest | None = None, value: str | None = None) -> str:
    """Resolve ``value`` (or the configured setting) to a Flower base URL.

    Absolute URLs are returned unchanged. Relative paths (the default
    ``/flower``) are made absolute against the current ``request`` so the link
    automatically follows the host/scheme the admin is served from. Without a
    request the relative path is returned as-is and resolved by the browser.
    """
    value = resolve_flower_setting() if value is None else value
    if not value:
        value = DEFAULT_FLOWER_ADDRESS
    value = value.rstrip("/")
    if urlparse(value).netloc:
        return value
    if not value.startswith("/"):
        value = "/" + value
    if request is not None:
        return request.build_absolute_uri(f"{value}/").rstrip("/")
    return value
