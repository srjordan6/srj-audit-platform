"""Template context for third-party analytics tags.

Supplies two things to every template:

1. `analytics_enabled` — whether this request is on a production hostname.
   Single source of truth for the host gate. Before this existed the same
   `request.get_host == "..." or ...` condition was pasted into each
   analytics partial, which is how the "Cookie settings" footer link ended
   up rendering on dev where there is no banner for it to open.

2. `ga4_pillar` / `ga4_section` — the two GA4 custom dimensions, derived
   from the request path so no view has to remember to set them and every
   page, current and future, is dimensioned automatically.

       /                     -> pillar "home"      section "home"
       /aiscore/             -> pillar "aiscore"   section "aiscore"
       /q/score/             -> pillar "q"         section "q/score"
       /q/score/log/         -> pillar "q"         section "q/score"
       /dashboard/eng/3/     -> pillar "dashboard" section "dashboard/eng"

   The template maps these onto the GA4 parameter names `pillar` and
   `section`, which are what the custom dimensions in the GA4 admin are
   registered against.

Registered in TEMPLATES['OPTIONS']['context_processors'] in
audit_platform/settings/base.py.
"""
from django.conf import settings


_HOME = "home"

# Fallback if ANALYTICS_HOSTS is absent from settings — fail closed, so a
# missing setting means no tracking rather than tracking everywhere.
_DEFAULT_HOSTS = ()


def _segments(path):
    """Return the non-empty path segments of `path`."""
    return [seg for seg in (path or "").split("/") if seg]


def ga4_dimensions(request):
    """Host gate + GA4 `pillar` / `section` for the current request.

    `pillar` is the first path segment, or "home" at the root.
    `section` is the first two segments joined by "/", falling back to the
    pillar when the path is only one level deep.
    """
    hosts = getattr(settings, "ANALYTICS_HOSTS", _DEFAULT_HOSTS)
    try:
        host = request.get_host()
    except Exception:
        # get_host() raises DisallowedHost on a bad Host header. Anything
        # we cannot identify is treated as not-production.
        host = ""

    context = {"analytics_enabled": host in hosts}

    segments = _segments(getattr(request, "path", ""))
    if not segments:
        context["ga4_pillar"] = _HOME
        context["ga4_section"] = _HOME
        return context

    pillar = segments[0]
    context["ga4_pillar"] = pillar
    context["ga4_section"] = "/".join(segments[:2]) if len(segments) >= 2 else pillar
    return context
