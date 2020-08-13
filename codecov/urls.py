"""codecov URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from internal_api.constants import INTERNAL_API_PREFIX
import codecov.views as views
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', views.health),
    path('', views.health),
    path('<str:service>/<str:owner_username>/<str:repo_name>/', include("graphs.urls")),
]

urlpatterns.append(path(INTERNAL_API_PREFIX, include('internal_api.urls')))
urlpatterns.append(path('webhooks/', include('webhook_handlers.urls')))
# Use regex to make the trailing slash optional
urlpatterns.append(re_path('^validate/?', include('validate.urls')))
