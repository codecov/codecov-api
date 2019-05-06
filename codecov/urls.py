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

import internal_api.org.views
import internal_api.repo.views
import internal_api.pull.views
import internal_api.commit.views
import internal_api.branch.views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/orgs', internal_api.org.views.OrgsView.as_view()),
    path('api/<str:ownerid>/repos', internal_api.repo.views.RepoView.as_view()),
    path('api/<int:repoid>/pulls', internal_api.pull.views.RepoPullsView.as_view()),
    path('api/<int:repoid>/commits', internal_api.commit.views.RepoCommitsView.as_view()),
    path('api/<int:repoid>/branches', internal_api.branch.views.RepoBranchesView.as_view())
]
