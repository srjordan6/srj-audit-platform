"""/r/<token>/ -- invited-respondent magic links (Part B-1 S.4.1).

Separate from /q/ so rate limiting and monitoring can be configured per
surface.
"""

from django.urls import path

from questionnaire import views

urlpatterns = [
    path("<str:token>/", views.respondent_link, name="respondent_link"),
]
