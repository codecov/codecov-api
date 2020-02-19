from django.urls import path
from .views import ValidateYamlHandler


urlpatterns = [
    path('validate', ValidateYamlHandler.as_view(), name='validate-yaml'),
]
