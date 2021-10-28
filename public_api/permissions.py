from rest_framework.permissions import BasePermission


class PullUpdatePermission(BasePermission):
    def has_permission(self, request, view):
        return (
            request.auth
            and "upload" in request.auth.get_scopes()
            and view.repo in request.auth.get_repositories()
        )
