from django.urls import path, include

from internal_api.owner.views import ProfileView, OwnerViewSet
from internal_api.pull.views import PullViewSet
from internal_api.commit.views import CommitsViewSet
from internal_api.branch.views import BranchViewSet
from internal_api.repo.views import RepositoryViewSet
from internal_api.compare.views import CompareViewSet

from rest_framework.routers import DefaultRouter
from internal_api.compare.router import ComparisonRouter

owners_router = DefaultRouter()
owners_router.register(r'owners', OwnerViewSet, base_name='owners')

repos_router = DefaultRouter()
repos_router.register(r'repos', RepositoryViewSet, base_name='repos')

repository_artifacts_router = DefaultRouter()
repository_artifacts_router.register(r'pulls', PullViewSet, base_name='pulls')
repository_artifacts_router.register(r'commits', CommitsViewSet, base_name='commits')
repository_artifacts_router.register(r'branches', BranchViewSet, base_name='branches')

compare_router = ComparisonRouter()
compare_router.register(r'compare', CompareViewSet, base_name='compare')

urlpatterns = [
    path('profile', ProfileView.as_view()),
    path('<str:service>/', include(owners_router.urls)),
    path('<str:service>/<str:orgName>/', include(repos_router.urls)),
    path('<str:service>/<str:orgName>/<str:repoName>/', include(repository_artifacts_router.urls)),
    path('<str:service>/<str:orgName>/<str:repoName>/', include(compare_router.urls))
]
