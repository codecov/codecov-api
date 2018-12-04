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
from django.urls import path

import internal_api.views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/pulls/', internal_api.views.PullRequestList.as_view()),
    path('api/commits/', internal_api.views.CommitList.as_view()),
    path('api/repos/', internal_api.views.RepositoryList.as_view()),
    path('api/repos/<int:repoid>/pulls', internal_api.views.RepoPullRequestList.as_view()),
    path('api/repos/<int:repoid>/commits', internal_api.views.RepoCommitList.as_view()),
]
