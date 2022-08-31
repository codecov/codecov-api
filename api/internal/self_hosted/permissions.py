from rest_framework.permissions import BasePermission

import services.self_hosted as self_hosted


class AdminPermissions(BasePermission):
    def has_permission(self, request, view):
        return self_hosted.is_admin_owner(request.user)
