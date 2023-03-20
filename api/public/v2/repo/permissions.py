from rest_framework.permissions import BasePermission

from codecov_auth.helpers import current_user_part_of_org


class RepositoryOrgMemberPermissions(BasePermission):
    def has_permission(self, request, view):
        return current_user_part_of_org(request.user, view.repo.author)
