from django.urls import path, include

from internal_api.owner.views import OwnerView
from internal_api.pull.views import RepoPullViewset

from internal_api.commit.views import RepoCommitList
from internal_api.branch.views import RepoBranchList

from internal_api.repo.views import RepositoryViewSet

from internal_api.account.views import AccountViewSet

from internal_api.compare.views import CompareViewSet

from rest_framework.routers import DefaultRouter
from internal_api.compare.router import ComparisonRouter


repos_router = DefaultRouter()
repos_router.register(r'', RepositoryViewSet, base_name='repos')

# Pull

pulls_router = DefaultRouter()
pulls_router.register(r'pulls', RepoPullViewset, base_name='pulls')

# Account

accounts_router = DefaultRouter()
accounts_router.register(r'accounts', AccountViewSet, base_name='accounts')

compare_router = ComparisonRouter()
compare_router.register(r'compare', CompareViewSet, base_name='compare')

commits_patterns = [
    path('', RepoCommitList.as_view(), name='commits-list'),
]

urlpatterns = [
    path('profile', OwnerView.as_view()),
    path('<str:orgName>/repos/', include(repos_router.urls)),
    path('', include(accounts_router.urls)),
    path('<str:orgName>/<str:repoName>/branches', RepoBranchList.as_view(), name="branches"),
    path('<str:orgName>/<str:repoName>/', include(pulls_router.urls)),
    path('<str:orgName>/<str:repoName>/commits', include(commits_patterns)),
    path('<str:orgName>/<str:repoName>/', include(compare_router.urls))
]
