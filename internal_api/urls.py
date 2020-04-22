from django.urls import path, include

from internal_api.owner.views import OwnerView
from internal_api.pull.views import PullViewSet
from internal_api.commit.views import CommitsViewSet
from internal_api.branch.views import BranchViewSet
from internal_api.repo.views import RepositoryViewSet
from internal_api.account.views import AccountViewSet
from internal_api.compare.views import CompareViewSet

from rest_framework.routers import DefaultRouter
from internal_api.compare.router import ComparisonRouter


repos_router = DefaultRouter()
repos_router.register(r'', RepositoryViewSet, base_name='repos')

repository_artifacts_router = DefaultRouter()
repository_artifacts_router.register(r'pulls', PullViewSet, base_name='pulls')
repository_artifacts_router.register(r'commits', CommitsViewSet, base_name='commits')
repository_artifacts_router.register(r'branches', BranchViewSet, base_name='branches')

accounts_router = DefaultRouter()
accounts_router.register(r'accounts', AccountViewSet, base_name='accounts')

compare_router = ComparisonRouter()
compare_router.register(r'compare', CompareViewSet, base_name='compare')

urlpatterns = [
    path('profile', OwnerView.as_view()),
    path('<str:orgName>/repos/', include(repos_router.urls)),
    path('<str:orgName>/<str:repoName>/', include(repository_artifacts_router.urls)),
    path('<str:orgName>/<str:repoName>/', include(compare_router.urls))
]
