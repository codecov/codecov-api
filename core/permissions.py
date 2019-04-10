from rest_framework.permissions import BasePermission


class IsRepoOwner(object):

    def is_user_owner_of_repo(self, user, repository):
        pass

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS