import abc
import logging

from django.conf import settings

import services.self_hosted as self_hosted
from codecov_auth.models import Owner
from services.segment import SegmentService

log = logging.getLogger(__name__)


class BaseActivator(abc.ABC):
    def __init__(self, org: Owner, user: Owner):
        self.org = org
        self.user = user

    @abc.abstractmethod
    def is_autoactivation_enabled(self) -> bool:
        pass

    @abc.abstractmethod
    def can_activate_user(self) -> bool:
        pass

    @abc.abstractmethod
    def activate_user(self):
        pass

    @abc.abstractmethod
    def is_activated(self) -> bool:
        pass


class CloudActivator(BaseActivator):
    def is_autoactivation_enabled(self) -> bool:
        return self.org.plan_auto_activate

    def can_activate_user(self) -> bool:
        return self.org.can_activate_user(self.user)

    def activate_user(self):
        self.org.activate_user(self.user)

    def is_activated(self) -> bool:
        return self.user.pk in self.org.plan_activated_users


class SelfHostedActivator(BaseActivator):
    def is_autoactivation_enabled(self) -> bool:
        return self_hosted.is_autoactivation_enabled()

    def can_activate_user(self) -> bool:
        return self_hosted.can_activate_owner(self.user)

    def activate_user(self):
        return self_hosted.activate_owner(self.user)

    def is_activated(self) -> bool:
        return self_hosted.is_activated_owner(self.user)


def _get_activator(org: Owner, user: Owner) -> BaseActivator:
    if settings.IS_ENTERPRISE:
        return SelfHostedActivator(org, user)
    else:
        return CloudActivator(org, user)


def try_auto_activate(org: Owner, user: Owner) -> bool:
    """
    Returns true iff the user was able to be activated, false otherwise.
    """

    activator = _get_activator(org, user)

    if activator.is_autoactivation_enabled():
        log.info(f"Attemping to auto-activate user {user.ownerid} in {org.ownerid}")
        if activator.can_activate_user():
            activator.activate_user()
            SegmentService().account_activated_user(
                current_user_ownerid=user.ownerid,
                ownerid_to_activate=user.ownerid,
                org_ownerid=org.ownerid,
                auto_activated=True,
            )
            return True
        else:
            log.info("Auto-activation failed -- not enough seats remaining")
    return False


def is_activated(org: Owner, user: Owner) -> bool:
    activator = _get_activator(org, user)
    return activator.is_activated()
