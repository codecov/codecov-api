from django.urls import path, include

from internal_api.owner.views import OwnerView
from internal_api.pull.views import RepoPullFlagsList, RepoPullViewset

from internal_api.commit.views import RepoCommitList, RepoCommitFlags
from internal_api.branch.views import RepoBranchList

from internal_api.repo.views import RepositoryViewSet

from internal_api.account.views import AccountViewSet

from internal_api.compare.views import CompareViewSet

from rest_framework.routers import DefaultRouter
from internal_api.compare.router import ComparisonRouter


repos_router = DefaultRouter()
repos_router.register(r'', RepositoryViewSet, base_name='repos')

# Pull

pull_router = DefaultRouter()
pull_router.register(r'', RepoPullViewset, base_name='pulls')

# Account

accounts_router = DefaultRouter()
accounts_router.register(r'accounts', AccountViewSet, base_name='accounts')

compare_router = ComparisonRouter()
compare_router.register(r'compare', CompareViewSet, base_name='compare')

commits_patterns = [
    path('', RepoCommitList.as_view(), name='commits-list'),
    path('/<str:commitid>/flags', RepoCommitFlags.as_view(), name='commits-flags-list'),
]

pulls_patterns = [
    path('/', include(pull_router.urls)),
    path('/<str:pullid>/flags', RepoPullFlagsList.as_view(), name='pulls-flags-list'),
]

urlpatterns = [
    path('profile', OwnerView.as_view()),
    path('<str:orgName>/repos/', include(repos_router.urls)),
    path('', include(accounts_router.urls)),
    path('<str:orgName>/<str:repoName>/branches', RepoBranchList.as_view(), name="branches"),
    path('<str:orgName>/<str:repoName>/pulls', include(pulls_patterns)),
    path('<str:orgName>/<str:repoName>/commits', include(commits_patterns)),
    path('<str:orgName>/<str:repoName>/', include(compare_router.urls))
]
