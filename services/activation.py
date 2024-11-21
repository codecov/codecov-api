import abc
import logging

from django.conf import settings

import services.self_hosted as self_hosted
from codecov_auth.models import Owner

log = logging.getLogger(__name__)


class BaseActivator(abc.ABC):
    def __init__(self, org: Owner, owner: Owner):
        self.org = org
        self.owner = owner

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
        return self.org.can_activate_user(self.owner)

    def activate_user(self):
        self.org.activate_user(self.owner)

    def is_activated(self) -> bool:
        if not self.org.plan_activated_users:
            return False

        return self.owner.pk in self.org.plan_activated_users


class SelfHostedActivator(BaseActivator):
    def is_autoactivation_enabled(self) -> bool:
        return self_hosted.is_autoactivation_enabled()

    def can_activate_user(self) -> bool:
        return self_hosted.can_activate_owner(self.owner)

    def activate_user(self):
        return self_hosted.activate_owner(self.owner)

    def is_activated(self) -> bool:
        return self_hosted.is_activated_owner(self.owner)


def _get_activator(org: Owner, owner: Owner) -> BaseActivator:
    if settings.IS_ENTERPRISE:
        return SelfHostedActivator(org, owner)
    else:
        return CloudActivator(org, owner)


def try_auto_activate(org: Owner, owner: Owner) -> bool:
    """
    Returns true if the user was able to be activated, false otherwise.
    """
    activator = _get_activator(org, owner)

    if activator.is_autoactivation_enabled():
        log.info(f"Attemping to auto-activate user {owner.ownerid} in {org.ownerid}")
        if activator.can_activate_user():
            activator.activate_user()
            return True
        else:
            log.info("Auto-activation failed -- not enough seats remaining")
    return False


def is_activated(org: Owner, owner: Owner) -> bool:
    activator = _get_activator(org, owner)
    return activator.is_activated()
