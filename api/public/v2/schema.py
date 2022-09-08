from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter

from codecov_auth.models import Service

service_parameter = OpenApiParameter(
    "service",
    OpenApiTypes.STR,
    OpenApiParameter.PATH,
    description="Git hosting service provider",
    enum=[name for name, desc in Service.choices],
)

owner_username_parameter = OpenApiParameter(
    "owner_username",
    OpenApiTypes.STR,
    OpenApiParameter.PATH,
    description="username from service provider",
)

repo_name_parameter = OpenApiParameter(
    "repo_name",
    OpenApiTypes.STR,
    OpenApiParameter.PATH,
    description="repository name",
)

owner_parameters = [service_parameter, owner_username_parameter]
repo_parameters = owner_parameters + [repo_name_parameter]
