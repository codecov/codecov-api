from django.urls import path

from .views import ValidateYamlHandler

urlpatterns = [
    path("", ValidateYamlHandler.as_view(), name="validate-yaml"),
]
