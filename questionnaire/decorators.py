"""Edit-blocking decorators for questionnaire write endpoints.

Enforces OD-18 §2.3/§2.4: Locked and Expired snapshots reject all writes.
Applied to submit_response and attest views in views.py.
"""

from __future__ import annotations

from functools import wraps

from django.db import connection
from django.http import HttpResponseForbidden, HttpResponseNotFound

from engagements import lifecycle
from questionnaire import services


def require_writable_state(view_func):
    """Reject POST if the respondent's engagement is Locked or Expired.

    Order of checks:
    1. Resolve respondent_id from session or GET param → 404 if absent
    2. Query snapshot_state → 404 if respondent unknown
    3. Check is_writable(state) → 403 if Locked/Expired

    Preserves the existing view's signature; the wrapped function is only
    called when state is Draft or Editable.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        rid = (
            request.session.get("respondent_id")
            or request.GET.get("respondent_id")
        )
        if not rid:
            return HttpResponseNotFound("respondent_id required")

        with connection.cursor() as cursor:
            state = services.get_engagement_state(cursor, rid)

        if state is None:
            return HttpResponseNotFound("respondent not found")

        if not lifecycle.is_writable(state):
            return HttpResponseForbidden(
                f"Cannot edit — snapshot is {state}. "
                f"Purchase a new $399 snapshot to reassess."
            )

        return view_func(request, *args, **kwargs)

    return wrapper
