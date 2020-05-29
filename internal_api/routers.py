from rest_framework.routers import DefaultRouter, Route, DynamicRoute


class RetrieveUpdateDestroyRouter(DefaultRouter):
    """
    A router that maps GET /resource/ -> retrieve, as opposed to list.

    Also maps

    PUT /resource/ -> to update
    PATCH /resource/ -> to partial_update
    DELETE /resource/ -> to destroy
    """
    routes = [
        Route(
            url=r'^{prefix}{trailing_slash}$',
            mapping={
                'get': 'retrieve',
                'put': 'update',
                'patch': 'partial_update',
                'delete': 'destroy'
            },
            name='{basename}-detail',
            detail=False,
            initkwargs={'suffix': 'Retrieve'}
        ),
        DynamicRoute(
            url=r'^{prefix}/{url_path}$',
            name='{basename}-{url_name}',
            detail=False,
            initkwargs={}
        )
    ]
