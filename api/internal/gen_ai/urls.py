from django.urls import path

from .views import GenAIAuthView

urlpatterns = [
    path("", GenAIAuthView.as_view(), name="gen-ai-auth"),
]
