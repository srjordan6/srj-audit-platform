from django.urls import path

from dashboard import views


app_name = "dashboard"


urlpatterns = [
    path("", views.engagement_list, name="engagement_list"),
    path("engagement/<uuid:engagement_id>/", views.engagement_detail, name="engagement_detail"),
    path("engagement/<uuid:engagement_id>/note/", views.engagement_add_note, name="engagement_add_note"),
    path("analytics/", views.analytics, name="analytics"),
]
