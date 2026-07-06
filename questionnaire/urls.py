"""URL routing for questionnaire app."""

from django.urls import path

from questionnaire import views


app_name = "questionnaire"


urlpatterns = [
    path("start/", views.start, name="start"),
    path("attest/", views.attest, name="attest"),
    path("resume/<str:token>/", views.resume, name="resume"),
    path("next/", views.next_question, name="next_question"),
    path("submit/", views.submit_response, name="submit_response"),
]