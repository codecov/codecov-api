import operator
from functools import reduce

from django.conf import settings
from django.db import transaction
from django.db.models import F, Func, Q, QuerySet
from shared.license import get_current_license

from codecov_auth.models import Owner
from services import ServiceException
from utils.config import get_config


class LicenseException(ServiceException):
    pass


def admin_owners() -> QuerySet:
    """
    Returns a queryset of admin owners based on the YAML config:

        setup:
          admins:
            - service: <provider>
              username: <username>
            - ...
    """
    admins = get_config("setup", "admins", default=[])

    filters = [
        Q(service=admin["service"], username=admin["username"])
        for admin in admins
        if "service" in admin and "username" in admin
    ]

    if len(filters) == 0:
        return Owner.objects.none()
    else:
        return Owner.objects.filter(reduce(operator.or_, filters))


def is_admin_owner(owner: Owner) -> bool:
    """
    Returns true iff the given owner is an admin.
    """
    return admin_owners().filter(pk=owner.pk).exists()


def activated_owners() -> QuerySet:
    """
    Returns all owners that are activated in ANY org's `plan_activated_users`
    across the entire instance.
    """
    owner_ids = (
        Owner.objects.annotate(
            plan_activated_owner_ids=Func(
                F("plan_activated_users"),
                function="unnest",
            )
        )
        .values_list("plan_activated_owner_ids", flat=True)
        .distinct()
    )

    return Owner.objects.filter(pk__in=owner_ids)


def is_activated_owner(owner: Owner) -> bool:
    """
    Returns true iff the given owner is activated in this instance.
    """
    return activated_owners().filter(pk=owner.pk).exists()


def license_seats() -> int:
    """
    Max number of seats allowed by the current license.
    """
    license = get_current_license()
    return license.number_allowed_users or 0


def can_activate_owner(owner: Owner) -> bool:
    """
    Returns true iff there are available seats left for activation.
    """
    if is_activated_owner(owner):
        # user is already activated in at least 1 org
        return True
    else:
        return activated_owners().count() < license_seats()


@transaction.atomic
def activate_owner(owner: Owner):
    """
    Activate the given owner in ALL orgs that the owner is a part of.
    """
    if not settings.IS_ENTERPRISE:
        raise Exception("activate_owner is only available in self-hosted environments")

    if not can_activate_owner(owner):
        raise LicenseException(
            "No seats remaining. Please contact Codecov support or deactivate users."
        )

    Owner.objects.filter(pk__in=owner.organizations).update(
        plan_activated_users=Func(
            owner.pk,
            function="array_append_unique",
            template="%(function)s(plan_activated_users, %(expressions)s)",
        )
    )


def deactivate_owner(owner: Owner):
    """
    Deactivate the given owner across ALL orgs.
    """
    if not settings.IS_ENTERPRISE:
        raise Exception(
            "deactivate_owner is only available in self-hosted environments"
        )

    Owner.objects.filter(
        plan_activated_users__contains=Func(
            owner.pk,
            function="array",
            template="%(function)s[%(expressions)s]",
        )
    ).update(
        plan_activated_users=Func(
            owner.pk,
            function="array_remove",
            template="%(function)s(plan_activated_users, %(expressions)s)",
        )
    )


def enable_autoactivation():
    """
    Enable auto-activation for the entire instance.

    There's no good place to store this instance-wide so we're just saving this
    for all owners.
    """
    Owner.objects.all().update(plan_auto_activate=True)


def disable_autoactivation():
    """
    Disable auto-activation for the entire instance.

    There's no good place to store this instance-wide so we're just saving this
    for all owners.
    """
    Owner.objects.all().update(plan_auto_activate=False)


def is_autoactivation_enabled():
    """
    Returns true if ANY org has auto-activation enabled.
    """
    return Owner.objects.filter(plan_auto_activate=True).exists()
