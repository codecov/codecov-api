from django.urls import path

import internal_api.org.views
import internal_api.repo.views
import internal_api.pull.views
import internal_api.commit.views
import internal_api.branch.views
import internal_api.compare.views


urlpatterns = [
    path('orgs', internal_api.org.views.OrgsView.as_view()),
    path('<str:orgName>/repos', internal_api.repo.views.RepositoryList.as_view()),
    path('<str:orgName>/<str:repoName>/details', internal_api.repo.views.RepositoryDetails.as_view()),
    path('<str:orgName>/<str:repoName>/regenerate-upload-token', internal_api.repo.views.RepositoryRegenerateUploadToken.as_view()),
    path('<str:orgName>/<str:repoName>/pulls', internal_api.pull.views.RepoPullList.as_view()),
    path('<str:orgName>/<str:repoName>/commits',
         internal_api.commit.views.RepoCommitList.as_view()),
    path('<str:orgName>/<str:repoName>/commits/<str:commitid>/flags',
         internal_api.commit.views.RepoCommitFlags.as_view()),
    path('<str:orgName>/<str:repoName>/branches',
         internal_api.branch.views.RepoBranchList.as_view()),
    path('<str:orgName>/<str:repoName>/compare/<str:base>...<str:head>/commits',
         internal_api.compare.views.CompareCommits.as_view()),
    path('<str:orgName>/<str:repoName>/compare/<str:base>...<str:head>/files',
         internal_api.compare.views.CompareFiles.as_view(), {'coverage_level': 'files'}),
    path('<str:orgName>/<str:repoName>/compare/<str:base>...<str:head>/lines',
         internal_api.compare.views.CompareFiles.as_view(), {'coverage_level': 'lines'}),
]
