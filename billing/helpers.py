from django.conf import settings
from django.db.models import QuerySet
from shared.plan.constants import ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS

from codecov_auth.models import Owner


def on_enterprise_plan(owner: Owner) -> bool:
    return settings.IS_ENTERPRISE or (
        owner.plan in ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS.keys()
    )


def get_all_admins_for_owners(owners: QuerySet[Owner]):
    admin_ids = set()
    for owner in owners:
        if owner.admins:
            admin_ids.update(owner.admins)

        # Add the owner's email as well - for user owners, admins is empty.
        if owner.email:
            admin_ids.add(owner.ownerid)

    admins: QuerySet[Owner] = Owner.objects.filter(pk__in=admin_ids)
    return admins
