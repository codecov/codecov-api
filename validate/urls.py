from django.urls import path

from .views import V1ValidateYamlHandler, V2ValidateYamlHandler

urlpatterns = [
    path("", V1ValidateYamlHandler.as_view(), name="validate-yaml"),
    path("v1", V1ValidateYamlHandler.as_view(), name="validate-yaml-v1"),
    path("v2", V2ValidateYamlHandler.as_view(), name="validate-yaml-v2"),
]
