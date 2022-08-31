from rest_framework.permissions import BasePermission


class SpecificScopePermission(BasePermission):
    def has_permission(self, request, view):
        return request.auth is not None and all(
            scope in request.auth.get_scopes() for scope in view.required_scopes
        )
