from django.urls import path

from engagements import buyer_views

app_name = "engagements"

urlpatterns = [
    path("reminders/run/", buyer_views.run_reminders, name="run_reminders"),
    path("login/", buyer_views.buyer_login, name="buyer_login"),
    path("<uuid:engagement_id>/respondents/", buyer_views.respondents, name="respondents"),
    path("<uuid:engagement_id>/respondents/add/", buyer_views.add_respondent, name="add_respondent"),
    path("<uuid:engagement_id>/respondents/<uuid:respondent_id>/nudge/",
         buyer_views.nudge_respondent, name="nudge_respondent"),
    path("<uuid:engagement_id>/respondents/<uuid:respondent_id>/remove/",
         buyer_views.remove_respondent, name="remove_respondent"),
]
