"""audit_platform URL configuration.

Top-level routing. App URLs are included by prefix:
- /                  → marketing landing + engagement creation (engagements app)
- /aiscore/          → AI Exposure Score screener, alias of /q/score/ (paid entry)
- /q/<token>/        → respondent questionnaire flow (questionnaire app)
- /r/<token>/        → Tier 2/3 respondent magic-link entry (questionnaire app)
- /billing/          → Stripe webhooks + checkout (billing app)
- /accounts/         → buyer authentication (accounts app)
- /admin/            → Django admin
- /healthz/          → Render health check
- /django-rq/        → background job dashboard (staff only in production)
"""
from django.contrib import admin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import include, path

from core.content_sync import content_sync_view
from questionnaire import views as q_views
from engagements.buyer_views import buyer_link


def healthz(request):
    """Liveness probe for Render. Returns 200 with body 'ok'."""
    return HttpResponse("ok", content_type="text/plain")


def root(request):
    """Marketing landing page — hero + value bullets + CTA to /q/start/."""
    return render(request, "marketing/landing.html", {})


urlpatterns = [
    path('', root, name='root'),
    # Public branded start URL — aiauditforcompanies.com/startaiaudit → questionnaire.views.start.
    # Alias of /q/start/; both routes render the same view. Marketing CTAs link here.
    path('startaiaudit/', q_views.start, name='start_alias'),
    # Pillar II and the combined offer: same view, instrument fixed by the URL.
    path('startsecurityaudit/', q_views.start_aiitsa, name='start_aiitsa'),
    path('startbothaudits/', q_views.start_combined, name='start_combined'),
    # Tier 2, the Self-Service Audit: same form, lands on the respondents dashboard.
    path('starttier2/', q_views.start_tier2, name='start_tier2'),
    # Public branded funnel entry — aiauditforcompanies.com/aiscore → the
    # 5-question AI Exposure Score screener. Alias of /q/score/; both routes
    # render the same view. Paid social points here, not at /startaiaudit.
    path('aiscore/', q_views.exposure_score, name='aiscore_alias'),
    path('admin/', admin.site.urls),
    path('healthz/', healthz, name='healthz'),
    # WordPress content sync (srj-audit-sync plugin pushes here weekly).
    # HMAC-authenticated via CONTENT_SYNC_SECRET; see core/content_sync.py.
    path('api/content-sync/', content_sync_view, name='content_sync'),
    path('django-rq/', include('django_rq.urls')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    # The following includes will be enabled as each app is built.
    # path('', include('engagements.urls')),
    path('q/', include('questionnaire.urls', namespace='questionnaire')),
    path('reports/', include('reports.urls', namespace='reports')),
    path('r/', include('questionnaire.respondent_urls')),
    path('e/', include('engagements.urls', namespace='engagements')),
    path('e/link/<str:token>/', buyer_link, name='buyer_link'),
    path('billing/', include('billing.urls', namespace='billing')),
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),
]
