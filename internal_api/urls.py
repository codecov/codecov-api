from django.urls import path, include
from django.conf import urls

from internal_api.owner.views import (
    ProfileView,
    OwnerViewSet,
    UserViewSet,
    InvoiceViewSet,
    AccountDetailsViewSet,
    PlanViewSet
)
from internal_api.pull.views import PullViewSet
from internal_api.commit.views import CommitsViewSet
from internal_api.branch.views import BranchViewSet
from internal_api.repo.views import RepositoryViewSet
from internal_api.compare.views import CompareViewSet

from rest_framework.routers import DefaultRouter
from rest_framework.exceptions import server_error

from .routers import RetrieveUpdateDestroyRouter
from .error_views import not_found


urls.handler404 = not_found
urls.handler500 = server_error

plans_router = DefaultRouter()
plans_router.register(r'plans', PlanViewSet, base_name='plans')

owners_router = DefaultRouter()
owners_router.register(r'owners', OwnerViewSet, base_name='owners')

owner_artifacts_router = DefaultRouter()
owner_artifacts_router.register(r'users', UserViewSet, base_name='users')
owner_artifacts_router.register(r'invoices', InvoiceViewSet, base_name='invoices')

account_details_router = RetrieveUpdateDestroyRouter()
account_details_router.register(r'account-details', AccountDetailsViewSet, base_name='account_details')

# TODO(pierce): roll this into owner_artifacts_router
repository_router = DefaultRouter()
repository_router.register(r'repos', RepositoryViewSet, base_name='repos')

repository_artifacts_router = DefaultRouter()
repository_artifacts_router.register(r'pulls', PullViewSet, base_name='pulls')
repository_artifacts_router.register(r'commits', CommitsViewSet, base_name='commits')
repository_artifacts_router.register(r'branches', BranchViewSet, base_name='branches')

compare_router = RetrieveUpdateDestroyRouter()
compare_router.register(r'compare', CompareViewSet, base_name='compare')

urlpatterns = [
    path('profile', ProfileView.as_view()),
    path('', include(plans_router.urls)),
    path('<str:service>/', include(owners_router.urls)),
    path('<str:service>/<str:owner_username>/', include(owner_artifacts_router.urls)),
    path('<str:service>/<str:owner_username>/', include(account_details_router.urls)),
    path('<str:service>/<str:orgName>/', include(repository_router.urls)),
    path('<str:service>/<str:orgName>/<str:repoName>/', include(repository_artifacts_router.urls)),
    path('<str:service>/<str:orgName>/<str:repoName>/', include(compare_router.urls))
]
