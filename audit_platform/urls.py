"""audit_platform URL configuration.

Top-level routing. App URLs are included by prefix:
- /                  → marketing landing + engagement creation (engagements app)
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


def healthz(request):
    """Liveness probe for Render. Returns 200 with body 'ok'."""
    return HttpResponse("ok", content_type="text/plain")


def root(request):
    """Marketing landing page — hero + value bullets + CTA to /q/start/."""
    return render(request, "marketing/landing.html", {})


urlpatterns = [
    path('', root, name='root'),
    path('admin/', admin.site.urls),
    path('healthz/', healthz, name='healthz'),
    path('django-rq/', include('django_rq.urls')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    # The following includes will be enabled as each app is built.
    # path('', include('engagements.urls')),
    path('q/', include('questionnaire.urls', namespace='questionnaire')),
    # path('r/', include('questionnaire.respondent_urls')),
    path('billing/', include('billing.urls', namespace='billing')),
]
