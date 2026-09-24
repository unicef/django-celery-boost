from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django_celery_boost.utils import get_flower_address

if TYPE_CHECKING:
    from django.http import HttpRequest


def flower(request: HttpRequest) -> dict[str, Any]:
    """Expose the resolved Flower base URL to all templates as ``flower_addr``."""
    return {"flower_addr": get_flower_address(request)}
