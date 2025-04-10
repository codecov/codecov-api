from asgiref.sync import sync_to_async
from django.conf import settings

import services.self_hosted as self_hosted
from api.shared.permissions import is_admin_on_provider
from codecov.commands.base import BaseInteractor


class GetIsCurrentUserAnAdminInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, owner, current_owner):
        if settings.IS_ENTERPRISE:
            return self_hosted.is_admin_owner(current_owner)
        else:
            if not current_owner:
                return False
            admins = owner.admins
            if not hasattr(current_owner, "ownerid"):
                return False
            if owner.ownerid == current_owner.ownerid:
                return True
            else:
                try:
                    isAdmin = is_admin_on_provider(current_owner, owner)
                    if isAdmin:
                        # save admin provider in admins list
                        owner.add_admin(current_owner)
                    return isAdmin or (current_owner.ownerid in admins)
                except Exception as error:
                    print("Error Calling Admin Provider " + repr(error))  # noqa: T201
                    return False
