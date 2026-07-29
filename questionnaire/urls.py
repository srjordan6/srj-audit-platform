"""URL routing for questionnaire app."""

from django.urls import path

from questionnaire import review_views, views


app_name = "questionnaire"


urlpatterns = [
    path("start/", views.start, name="start"),
    # Short entry funnel: 5 questions, no form wall, instant score.
    path("score/", views.exposure_score, name="exposure_score"),
    path("score/log/", views.exposure_score_log, name="exposure_score_log"),
    path("attest/", views.attest, name="attest"),
    path("resume/<str:token>/", views.resume, name="resume"),
    path("next/", views.next_question, name="next_question"),
    path("previous/", views.previous_question, name="previous_question"),
    path("forward/", views.forward_question, name="forward_question"),
    path("jump/", views.jump_to_position, name="jump_to_position"),
    path("recommend-laws-ai/", views.ai_recommend_laws_view, name="ai_recommend_laws"),
    path("submit/", views.submit_response, name="submit_response"),
    path("review/", review_views.review, name="review"),
    path("edit/<str:question_id>/", review_views.edit_question, name="edit_question"),
    path("regenerate/", views.regenerate_report_view, name="regenerate_report"),
]
