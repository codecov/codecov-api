from rest_framework.routers import SimpleRouter, Route, DynamicRoute


class ComparisonRouter(SimpleRouter):
    routes = [
        Route(
            url=r'^{prefix}{trailing_slash}$',
            mapping={
                'get': 'retrieve',
            },
            name='{basename}-retrieve',
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
