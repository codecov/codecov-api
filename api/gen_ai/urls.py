from django.urls import path

from .views import GenAIAuthView

urlpatterns = [
    path("auth/", GenAIAuthView.as_view(), name="auth"),
]
