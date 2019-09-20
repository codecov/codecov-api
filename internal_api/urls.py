from django.urls import path, include

from internal_api.org.views import OrgsView
from internal_api.pull.views import RepoPullList, RepoPullFlagsList

from internal_api.commit.views import RepoCommitList, RepoCommitFlags
from internal_api.branch.views import RepoBranchList

from internal_api.repo.views import (
    RepositoryList,
    RepositoryDetails,
    RepositoryRegenerateUploadToken,
    RepositoryDefaultBranch,
)

from internal_api.compare.views import (
    CompareCommits,
    CompareFlagsList,
    CompareFullSource,
    CompareDetails,
    CompareSingleFileSource,
    CompareSingleFileDiff
)


repo_patterns = [
    path('details', RepositoryDetails.as_view(), name='details'),
    path('branches', RepoBranchList.as_view(), name='branches'),
    path('default-branch', RepositoryDefaultBranch.as_view(), name='default-branch'),
    path('regenerate-upload-token', RepositoryRegenerateUploadToken.as_view(), name='regen-upload-token'),
]


commits_patterns = [
    path('', RepoCommitList.as_view(), name='commits-list'),
    path('/<str:commitid>/flags', RepoCommitFlags.as_view(), name='commits-flags-list'),
]


pulls_patterns = [
    path('', RepoPullList.as_view(), name='pulls-list'),
    path('/<str:pullid>/flags', RepoPullFlagsList.as_view(), name='pulls-flags-list'),
]


compare_patterns = [
    path('commits', CompareCommits.as_view(), name='compare-commits'),
    path('flags', CompareFlagsList.as_view(), name='compare-flags'),
    path('src', CompareFullSource.as_view(), name='compare-src-full'),
    path('details', CompareDetails.as_view(), name='compare-details'),
    path('src_file/<path:file_path>', CompareSingleFileSource.as_view(), name='compare-src-file'),
    path('diff_file/<path:file_path>', CompareSingleFileDiff.as_view(), name='compare-diff-file'),
]


urlpatterns = [
    path('orgs', OrgsView.as_view()),
    path('<str:orgName>/repos', RepositoryList.as_view()),
    path('<str:orgName>/<str:repoName>/', include(repo_patterns)),
    path('<str:orgName>/<str:repoName>/pulls', include(pulls_patterns)),
    path('<str:orgName>/<str:repoName>/commits', include(commits_patterns)),
    path('<str:orgName>/<str:repoName>/compare/', include(compare_patterns))
]
