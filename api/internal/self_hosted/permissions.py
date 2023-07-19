from rest_framework.permissions import BasePermission

import services.self_hosted as self_hosted


class AdminPermissions(BasePermission):
    def has_permission(self, request, view):
        return request.current_owner and self_hosted.is_admin_owner(
            request.current_owner
        )
