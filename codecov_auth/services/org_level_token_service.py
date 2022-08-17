import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.forms import ValidationError

from billing.constants import ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS
from codecov_auth.models import OrganizationLevelToken, Owner, TokenTypeChoices

log = logging.getLogger(__name__)


class OrgLevelTokenService(object):
    """
    Groups some basic CRUD functionality to create and delete OrganizationLevelToken.
    Restrictions:
        -- only Owners in ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS can have OrganizationLevelToken
        -- only 1 token per Owner
    """

    @classmethod
    def org_can_have_upload_token(cls, org: Owner):
        return org.plan in ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS

    @classmethod
    def get_or_create_org_token(cls, org: Owner):
        if not cls.org_can_have_upload_token(org):
            raise ValidationError(
                "Organization-wide upload tokens are only available in enterprise-cloud plans."
            )
        token, created = OrganizationLevelToken.objects.get_or_create(
            owner=org, token_type=TokenTypeChoices.UPLOAD
        )
        return token

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
    if owner_can_have_org_token:
        OrgLevelTokenService.get_or_create_org_token(instance)
    else:
        OrgLevelTokenService.delete_org_token_if_exists(instance)
