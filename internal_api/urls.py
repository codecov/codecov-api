from django.urls import path

import internal_api.org.views
import internal_api.repo.views
import internal_api.pull.views
import internal_api.commit.views
import internal_api.branch.views


urlpatterns = [
    path('<int:ownerid>/orgs', internal_api.org.views.OrgsView.as_view()),
    path('<int:ownerid>/repos', internal_api.repo.views.RepoView.as_view()),
    path('<int:repoid>/pulls', internal_api.pull.views.RepoPullsView.as_view()),
    path('<int:repoid>/commits',
         internal_api.commit.views.RepoCommitsView.as_view()),
    path('<int:repoid>/branches',
         internal_api.branch.views.RepoBranchesView.as_view())
]