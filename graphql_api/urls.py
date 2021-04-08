from django.urls import path

from .views import AriadneView

urlpatterns = [
    path("<str:service>", AriadneView, name="graphql"),
]
