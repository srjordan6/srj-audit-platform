"""URL routing for questionnaire app.

Mount into project urls.py via:
    path("q/", include("questionnaire.urls", namespace="questionnaire")),
"""

from django.urls import path

from questionnaire import views


app_name = "questionnaire"


urlpatterns = [
    path("next/", views.next_question, name="next_question"),
    path("submit/", views.submit_response, name="submit_response"),
]
