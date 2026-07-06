"""Edit-blocking decorators. All Django imports are lazy for test isolation."""

from __future__ import annotations

from functools import wraps

from engagements import lifecycle
from questionnaire import services


def _get_cursor_ctx():
    from django.db import connection
    return connection.cursor()


def _response_403(state):
    from django.http import HttpResponseForbidden
    return HttpResponseForbidden(
        (f"Cannot edit — snapshot is {state}. "
         f"Purchase a new $399 snapshot to reassess.").encode("utf-8")
    )


def _response_404(msg):
    from django.http import HttpResponseNotFound
    return HttpResponseNotFound(msg.encode("utf-8"))


def require_writable_state(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        rid = (
            request.session.get("respondent_id")
            or request.GET.get("respondent_id")
        )
        if not rid:
            return _response_404("respondent_id required")
        with _get_cursor_ctx() as cursor:
            state = services.get_engagement_state(cursor, rid)
        if state is None:
            return _response_404("respondent not found")
        if not lifecycle.is_writable(state):
            return _response_403(state)
        return view_func(request, *args, **kwargs)
    return wrapper