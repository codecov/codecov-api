from asgiref.sync import async_to_sync, sync_to_async
from django.conf import settings

import services.self_hosted as self_hosted
from codecov.commands.base import BaseInteractor
from services.decorators import torngit_safe
from services.repo_providers import get_generic_adapter_params, get_provider


@torngit_safe
@sync_to_async
def _is_admin_on_provider(owner, current_user):
    torngit_provider_adapter = get_provider(
        owner.service,
        {
            **get_generic_adapter_params(current_user, owner.service),
            **{
                "owner": {
                    "username": owner.username,
                    "service_id": owner.service_id,
                }
            },
        },
    )

    isAdmin = async_to_sync(torngit_provider_adapter.get_is_admin)(
        user={"username": current_user.username, "service_id": current_user.service_id}
    )
    return isAdmin


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
                    isAdmin = async_to_sync(_is_admin_on_provider)(owner, current_owner)
                    if isAdmin:
                        # save admin provider in admins list
                        owner.add_admin(current_owner)
                    return isAdmin or (current_owner.ownerid in admins)
                except Exception as error:
                    print("Error Calling Admin Provider " + repr(error))  # noqa: T201
                    return False
