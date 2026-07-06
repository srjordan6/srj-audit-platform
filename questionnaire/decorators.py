"""Edit-blocking decorators for questionnaire write endpoints.

Enforces OD-18 §2.3/§2.4: Locked and Expired snapshots reject all writes.
"""

from __future__ import annotations

from functools import wraps

from django.db import connection

from engagements import lifecycle
from questionnaire import services


def _response_403(state: str):
    """Build 403 without touching Django settings at import time."""
    from django.http import HttpResponseForbidden
    return HttpResponseForbidden(
        f"Cannot edit — snapshot is {state}. "
        f"Purchase a new $399 snapshot to reassess.".encode("utf-8")
    )


def _response_404(msg: str):
    from django.http import HttpResponseNotFound
    return HttpResponseNotFound(msg.encode("utf-8"))


def require_writable_state(view_func):
    """Reject POST if the respondent's engagement is Locked or Expired."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        rid = (
            request.session.get("respondent_id")
            or request.GET.get("respondent_id")
        )
        if not rid:
            return _response_404("respondent_id required")

        with connection.cursor() as cursor:
            state = services.get_engagement_state(cursor, rid)

        if state is None:
            return _response_404("respondent not found")

        if not lifecycle.is_writable(state):
            return _response_403(state)

        return view_func(request, *args, **kwargs)

    return wrapper