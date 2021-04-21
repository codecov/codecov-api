from django.urls import path

from .views import ariadne_view

urlpatterns = [
    path("<str:service>", ariadne_view, name="graphql"),
]
