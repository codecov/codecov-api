import logging
import uuid

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.forms import ValidationError

from codecov_auth.models import OrganizationLevelToken, Owner
from plan.constants import USER_PLAN_REPRESENTATIONS

log = logging.getLogger(__name__)


class OrgLevelTokenService(object):
    """
    Groups some basic CRUD functionality to create and delete OrganizationLevelToken.
    Restrictions:
        -- only 1 token per Owner
    """

    @classmethod
    def org_can_have_upload_token(cls, org: Owner):
        return org.plan in USER_PLAN_REPRESENTATIONS

    @classmethod
    def get_or_create_org_token(cls, org: Owner):
        if not cls.org_can_have_upload_token(org):
            raise ValidationError(
                "Organization-wide upload tokens are not available for your organization."
            )
        token, created = OrganizationLevelToken.objects.get_or_create(owner=org)
        if created:
            log.info(
                "New OrgLevelToken created",
                extra=dict(
                    ownerid=org.ownerid,
                    valid_until=token.valid_until,
                    token_type=token.token_type,
                ),
            )
        return token

    @classmethod
    def refresh_token(cls, tokenid: int):
        try:
            token = OrganizationLevelToken.objects.get(id=tokenid)
            token.token = uuid.uuid4()
            token.save()
        except OrganizationLevelToken.DoesNotExist:
            raise ValidationError(
                "Token to refresh was not found", params=dict(tokenid=tokenid)
            )

    @classmethod
    def delete_org_token_if_exists(cls, org: Owner):
        try:
            org_token = OrganizationLevelToken.objects.get(owner=org)
            org_token.delete()
        except OrganizationLevelToken.DoesNotExist:
            pass


@receiver(post_save, sender=Owner)
def manage_org_tokens_if_owner_plan_changed(sender, instance: Owner, **kwargs):
    """
    Gets executed after saving a Owner instance to DB.
    Manages OrganizationLevelToken according to Owner plan, either creating or deleting them as necessary
    """
    owner_can_have_org_token = OrgLevelTokenService.org_can_have_upload_token(instance)
    if not owner_can_have_org_token:
        OrgLevelTokenService.delete_org_token_if_exists(instance)
