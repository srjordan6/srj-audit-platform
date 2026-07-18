"""URL routing for the reports app (Phase 2e download)."""

from django.urls import path

from reports import download_views

app_name = "reports"

urlpatterns = [
    path("mine/download/", download_views.download_my_report,
         name="download_my_report"),
]
