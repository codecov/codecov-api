from asgiref.sync import async_to_sync, sync_to_async

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
    def execute(self, owner, current_user):
        admins = owner.admins
        if owner.ownerid == current_user.ownerid:
            return True
        elif admins and bool(admins[0]):
            return current_user.ownerid in admins
        else:
            try:
                isAdmin = async_to_sync(_is_admin_on_provider)(owner, current_user)
                if isAdmin:
                    # save admin provider in admins list
                    owner.admins.append(current_user.ownerid)
                    owner.save()
                return isAdmin
            except Exception as error:
                print("Error Calling Admin Provider " + repr(error))
                return False
