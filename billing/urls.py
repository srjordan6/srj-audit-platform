"""URL routing for billing app.

Mounted in project urls.py at /billing/.
"""

from django.urls import path

from billing import stripe_views


app_name = "billing"


urlpatterns = [
    path("checkout/", stripe_views.create_checkout, name="checkout"),
    path("checkout/tier2/<uuid:engagement_id>/", stripe_views.create_tier2_checkout, name="checkout_tier2"),
    path("webhook/", stripe_views.webhook, name="webhook"),
    path("success/", stripe_views.success, name="success"),
]
