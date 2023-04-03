from django.urls import path

from api.internal.slack.views import GenerateAccessTokenView

urlpatterns = [
    path("generate-token/", GenerateAccessTokenView.as_view(), name="generate-token"),
]
