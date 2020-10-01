from django.urls import path, include
from django.conf import urls

from internal_api.owner.views import (
    ProfileViewSet,
    OwnerViewSet,
    UserViewSet,
    InvoiceViewSet,
    AccountDetailsViewSet,
    PlanViewSet,
)
from internal_api.pull.views import PullViewSet
from internal_api.commit.views import CommitsViewSet
from internal_api.branch.views import BranchViewSet
from internal_api.repo.views import RepositoryViewSet
from internal_api.compare.views import CompareViewSet
from internal_api.sessions.views import SessionViewSet


from rest_framework.routers import DefaultRouter
from rest_framework.exceptions import server_error

from .routers import RetrieveUpdateDestroyRouter
from .error_views import not_found


urls.handler404 = not_found
urls.handler500 = server_error

plans_router = DefaultRouter()
plans_router.register(r"plans", PlanViewSet, basename="plans")

profile_router = RetrieveUpdateDestroyRouter()
profile_router.register(r"profile", ProfileViewSet, basename="profile")

owners_router = DefaultRouter()
owners_router.register(r"owners", OwnerViewSet, basename="owners")

owner_artifacts_router = DefaultRouter()
owner_artifacts_router.register(r'users', UserViewSet, basename='users')
owner_artifacts_router.register(r'invoices', InvoiceViewSet, basename='invoices')
owner_artifacts_router.register(r'repos', RepositoryViewSet, basename='repos')
owner_artifacts_router.register(r'sessions', SessionViewSet, basename='sessions')

account_details_router = RetrieveUpdateDestroyRouter()
account_details_router.register(
    r"account-details", AccountDetailsViewSet, basename="account_details"
)

repository_artifacts_router = DefaultRouter()
repository_artifacts_router.register(r"pulls", PullViewSet, basename="pulls")
repository_artifacts_router.register(r"commits", CommitsViewSet, basename="commits")
repository_artifacts_router.register(r"branches", BranchViewSet, basename="branches")

compare_router = RetrieveUpdateDestroyRouter()
compare_router.register(r"compare", CompareViewSet, basename="compare")

urlpatterns = [
    path('', include(plans_router.urls)),
    path('', include(profile_router.urls)),
    path('<str:service>/', include(owners_router.urls)),
    path('<str:service>/<str:owner_username>/', include(owner_artifacts_router.urls)),
    path('<str:service>/<str:owner_username>/', include(account_details_router.urls)),
    path('<str:service>/<str:owner_username>/<str:repo_name>/', include(repository_artifacts_router.urls)),
    path('<str:service>/<str:owner_username>/<str:repo_name>/', include(compare_router.urls)),
    path("charts/", include("internal_api.chart.urls"))
]
