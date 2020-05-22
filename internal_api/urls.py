from django.urls import path, include
from django.conf import urls

from internal_api.owner.views import ProfileView, OwnerViewSet, UserViewSet
from internal_api.pull.views import PullViewSet
from internal_api.commit.views import CommitsViewSet
from internal_api.branch.views import BranchViewSet
from internal_api.repo.views import RepositoryViewSet
from internal_api.compare.views import CompareViewSet

from rest_framework.routers import DefaultRouter
from rest_framework.exceptions import server_error

from .compare.router import ComparisonRouter
from .error_views import not_found


urls.handler404 = not_found
urls.handler500 = server_error

owners_router = DefaultRouter()
owners_router.register(r'owners', OwnerViewSet, base_name='owners')

users_router = DefaultRouter()
users_router.register(r'users', UserViewSet, base_name='users')

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
    path('<str:service>/owners/<str:username>/', include(users_router.urls)),
    path('<str:service>/<str:orgName>/', include(repos_router.urls)),
    path('<str:service>/<str:orgName>/<str:repoName>/', include(repository_artifacts_router.urls)),
    path('<str:service>/<str:orgName>/<str:repoName>/', include(compare_router.urls))
]
