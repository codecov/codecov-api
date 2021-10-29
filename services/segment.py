import logging
import re
from datetime import datetime
from enum import Enum

import analytics
from django.conf import settings

from codecov_auth.models import Owner

log = logging.getLogger(__name__)


BLANK_SEGMENT_USER_ID = "-1"


def on_segment_error(error):
    log.error(f"Segment error: {error}")


if settings.SEGMENT_ENABLED:
    if not settings.SEGMENT_API_KEY:
        log.warning("Segment enabled but segment API key not set")
    analytics.write_key = settings.SEGMENT_API_KEY
    analytics.debug = settings.DEBUG
    analytics.on_error = on_segment_error


def segment_enabled(method):
    """
    Decorator: checks that Segment is enabled before executing decorated method.
    Also ensures any exception that occurs during execution doesn't crash us.
    """

    def exec_method(*args, **kwargs):
        if settings.SEGMENT_ENABLED:
            try:
                return method(*args, **kwargs)
            except Exception as e:
                log.error(f"Segment raised an exception: {e}")

    return exec_method


def inject_segment_owner(method):
    """
    Decorator: promotes type of 'owner' arg to 'SegmentOwner'.
    """

    @segment_enabled
    def exec_method(self, owner, **kwargs):
        segment_owner = SegmentOwner(owner, cookies=kwargs.get("cookies", {}))
        return method(self, segment_owner, **kwargs)

    return exec_method


def inject_segment_repository(method):
    """
    Decorator: promotes type of second parameter (a repository) to SegmentRepository
    """

    @segment_enabled
    def exec_method(self, ownerid, repository):
        segment_repository = SegmentRepository(repository)
        return method(self, ownerid, segment_repository)

    return exec_method


class SegmentEvent(Enum):
    ACCOUNT_ACTIVATED_REPOSITORY_ON_UPLOAD = "Account Activated Repository On Upload"
    ACCOUNT_ACTIVATED_REPOSITORY = "Account Activated Repository"
    ACCOUNT_ACTIVATED_USER = "Account Activated User"
    ACCOUNT_ADDED_USER = "Account Added User"  # TODO: check with Jon how this is different from Account Activated User?
    ACCOUNT_CANCELLED_SUBSCRIPTION = "Account Cancelled Subscription"
    ACCOUNT_CHANGED_PLAN = "Account Changed Plan"
    ACCOUNT_COMPLETED_CHECKOUT = "Account Completed Checkout"
    ACCOUNT_CREATED = "Account Created"
    ACCOUNT_DEACTIVATED_REPOSITORY = "Account Deactivated Repository"
    ACCOUNT_DEACTIVATED_USER = "Account Deactivated User"
    ACCOUNT_DECREASED_USERS = "Account Decreased Users"
    ACCOUNT_DELETED_REPOSITORY = "Account Deleted Repository"
    ACCOUNT_DELETED = "Account Deleted"
    ACCOUNT_ERASED_REPOSITORY = "Account Erased Repository"
    ACCOUNT_INCREASED_USERS = "Account Increased Users"
    ACCOUNT_INSTALLED_SOURCE_CONTROL_APP = (
        "Account Installed Source Control Service App"
    )
    ACCOUNT_PAID_SUBSCRIPTION = "Account Paid Subscription"
    ACCOUNT_REMOVED_USER = "Account Removed User"  # TODO: check with Jon how this is different from Account Deactivated User?
    ACCOUNT_UNINSTALLED_SOURCE_CONTROL_APP = (
        "Account Uninstalled Source Control Service App"
    )
    ACCOUNT_UPLOADED_COVERAGE_REPORT = "Account Uploaded Coverage Report"
    TRIAL_ENDED = "Trial Ended"
    TRIAL_STARTED = "Trial Started"
    USER_SIGNED_IN = "User Signed In"
    USER_SIGNED_OUT = "User Signed Out"
    USER_SIGNED_UP = "User Signed Up"


class SegmentOwner:
    """
    An object wrapper around 'Owner' that provides "user_id", "traits",
    and "context" properties.
    """

    def __init__(self, owner, cookies={}, owner_collection_type="users"):
        self.owner = owner
        self.cookies = cookies
        self.owner_collection_type = owner_collection_type

    @property
    def user_id(self):
        return self.owner.ownerid

    @property
    def traits(self):
        return {
            "avatar": self.owner.avatar_url,
            "service": self.owner.service,
            "service_id": self.owner.service_id,
            "plan": self.owner.plan,
            "staff": self.owner.staff,
            "has_yaml": self.owner.yaml is not None,
            # Default values set to make the data readable by Salesforce
            "email": self.owner.email or "unknown@codecov.io",
            "name": self.owner.name or "unknown",
            "username": self.owner.username or "unknown",
            "student": self.owner.student or False,
            "bot": self.owner.bot or False,
            "delinquent": self.owner.delinquent or False,
            "did_trial": self.owner.did_trial or False,
            "private_access": self.owner.private_access or False,
            "plan_provider": self.owner.plan_provider or "",
            "plan_user_count": self.owner.plan_user_count or 5,
            # Set ms to 0 on dates to match date format required by Salesforce
            "createdAt": self.owner.createstamp.replace(microsecond=0)
            if self.owner.createstamp
            else datetime(2014, 1, 1, 12, 0, 0),
            "updatedAt": self.owner.updatestamp.replace(microsecond=0)
            if self.owner.updatestamp
            else datetime(2014, 1, 1, 12, 0, 0),
            "student_created_at": self.owner.student_created_at.replace(microsecond=0)
            if self.owner.student_created_at
            else datetime(2014, 1, 1, 12, 0, 0),
            "student_updated_at": self.owner.student_updated_at.replace(microsecond=0)
            if self.owner.student_updated_at
            else datetime(2014, 1, 1, 12, 0, 0),
        }

    @property
    def context(self):
        """
        Mostly copied from
        https://github.com/codecov/codecov.io/blob/master/app/services/analytics_tracking.py#L107
        """
        context = {"externalIds": []}

        context["externalIds"].append(
            {
                "id": self.owner.service_id,
                "type": f"{self.owner.service}_id",
                "collection": self.owner_collection_type,
                "encoding": "none",
            }
        )

        if self.owner.stripe_customer_id:
            context["externalIds"].append(
                {
                    "id": self.owner.stripe_customer_id,
                    "type": "stripe_customer_id",
                    "collection": self.owner_collection_type,
                    "encoding": "none",
                }
            )

        if self.cookies and self.owner_collection_type == "users":
            marketo_cookie = self.cookies.get("_mkto_trk")
            ga_cookie = self.cookies.get("_ga")
            if marketo_cookie:
                context["externalIds"].append(
                    {
                        "id": marketo_cookie,
                        "type": "marketo_cookie",
                        "collection": "users",
                        "encoding": "none",
                    }
                )
                context["Marketo"] = {"marketo_cookie": marketo_cookie}
            if ga_cookie:
                # id is everything after the "GA.1." prefix
                match = re.match("^.+\.(.+?\..+?)$", ga_cookie)
                if match:
                    ga_client_id = match.group(1)
                    context["externalIds"].append(
                        {
                            "id": ga_client_id,
                            "type": "ga_client_id",
                            "collection": "users",
                            "encoding": "none",
                        }
                    )

        return context


class SegmentRepository:
    """
    Wrapper object around Repository to provide a similar "traits" field as in SegmentOwner above.
    """

    def __init__(self, repo):
        self.repo = repo

    @property
    def traits(self):
        return {
            "repoid": self.repo.repoid,
            "ownerid": self.repo.author.ownerid,
            "service_id": self.repo.service_id,
            "name": self.repo.name,
            "private": self.repo.private,
            "branch": self.repo.branch,
            "updatestamp": self.repo.updatestamp,
            "language": self.repo.language,
            "active": self.repo.active,
            "deleted": self.repo.deleted,
            "activated": self.repo.activated,
            "bot": self.repo.bot,
            "using_integration": self.repo.using_integration,
            "hookid": self.repo.hookid,
            "has_yaml": self.repo.yaml is not None,
        }


class SegmentService:
    """
    Various methods for emitting events related to user actions.
    """

    @inject_segment_owner
    def identify_user(self, segment_owner, cookies=None):
        analytics.identify(
            segment_owner.user_id,
            segment_owner.traits,
            segment_owner.context,
            integrations={"Salesforce": True, "Marketo": False},
        )

    @segment_enabled
    def group(self, owner):
        if owner.organizations:
            organizations = Owner.objects.filter(ownerid__in=owner.organizations)
            for org in organizations:
                segment_organization = SegmentOwner(
                    org, owner_collection_type="accounts"
                )
                analytics.group(
                    user_id=owner.ownerid,
                    group_id=org.ownerid,
                    traits=segment_organization.traits,
                    context=segment_organization.context,
                )

    @inject_segment_owner
    def user_signed_up(self, segment_owner, **kwargs):
        event_properties = {
            **segment_owner.traits,
            "signup_department": kwargs.get("utm_department") or "marketing",
            "signup_campaign": kwargs.get("utm_campaign") or "",
            "signup_medium": kwargs.get("utm_medium") or "",
            "signup_source": kwargs.get("utm_source") or "direct",
            "signup_content": kwargs.get("utm_content") or "",
            "signup_term": kwargs.get("utm_term") or "",
        }
        analytics.track(
            segment_owner.user_id, SegmentEvent.USER_SIGNED_UP.value, event_properties,
        )

    @inject_segment_owner
    def user_signed_in(self, segment_owner, **kwargs):
        event_properties = {
            **segment_owner.traits,
            "signup_department": kwargs.get("utm_department") or "marketing",
            "signup_campaign": kwargs.get("utm_campaign") or "",
            "signup_medium": kwargs.get("utm_medium") or "",
            "signup_source": kwargs.get("utm_source") or "direct",
            "signup_content": kwargs.get("utm_content") or "",
            "signup_term": kwargs.get("utm_term") or "",
        }
        analytics.track(
            segment_owner.user_id, SegmentEvent.USER_SIGNED_IN.value, event_properties,
        )

    @inject_segment_owner
    def user_signed_out(self, segment_owner):
        analytics.track(
            segment_owner.user_id,
            SegmentEvent.USER_SIGNED_OUT.value,
            segment_owner.traits,
        )

    @inject_segment_owner
    def account_deleted(self, segment_owner):
        analytics.track(
            user_id=segment_owner.user_id,
            properties=segment_owner.traits,
            context={"groupId": segment_owner.user_id},
        )

    @inject_segment_repository
    def account_activated_repository(self, current_user_ownerid, segment_repository):
        analytics.track(
            user_id=current_user_ownerid,
            event=SegmentEvent.ACCOUNT_ACTIVATED_REPOSITORY.value,
            properties=segment_repository.traits,
            context={"groupId": segment_repository.repo.author.ownerid},
        )

    @inject_segment_repository
    def account_deactivated_repository(self, current_user_ownerid, segment_repository):
        analytics.track(
            user_id=current_user_ownerid,
            event=SegmentEvent.ACCOUNT_DEACTIVATED_REPOSITORY.value,
            properties=segment_repository.traits,
            context={"groupId": segment_repository.repo.author.ownerid},
        )

    @inject_segment_repository
    def account_erased_repository(self, current_user_ownerid, segment_repository):
        analytics.track(
            user_id=current_user_ownerid,
            event=SegmentEvent.ACCOUNT_ERASED_REPOSITORY.value,
            properties=segment_repository.traits,
            context={"groupId": segment_repository.repo.author.ownerid},
        )

    @inject_segment_repository
    def account_deleted_repository(self, current_user_ownerid, segment_repository):
        analytics.track(
            user_id=current_user_ownerid,
            event=SegmentEvent.ACCOUNT_DELETED_REPOSITORY.value,
            properties=segment_repository.traits,
            context={"groupId": segment_repository.repo.author.ownerid},
        )

    @inject_segment_repository
    def account_activated_repository_on_upload(self, org_ownerid, segment_repository):
        analytics.track(
            user_id=BLANK_SEGMENT_USER_ID,
            event=SegmentEvent.ACCOUNT_ACTIVATED_REPOSITORY_ON_UPLOAD.value,
            properties=segment_repository.traits,
            context={"groupId": org_ownerid},
        )

    @segment_enabled
    def account_activated_user(
        self,
        current_user_ownerid,
        ownerid_to_activate,
        org_ownerid,
        auto_activated=False,
    ):
        analytics.track(
            user_id=current_user_ownerid,
            event=SegmentEvent.ACCOUNT_ACTIVATED_USER.value,
            properties={
                "role": "admin",
                "user": ownerid_to_activate,
                "auto_activated": auto_activated,
            },
            context={"groupId": org_ownerid},
        )

    @segment_enabled
    def account_deactivated_user(
        self, current_user_ownerid, ownerid_to_deactivate, org_ownerid
    ):
        analytics.track(
            user_id=current_user_ownerid,
            event=SegmentEvent.ACCOUNT_DEACTIVATED_USER.value,
            properties={"role": "admin", "user": ownerid_to_deactivate,},
            context={"groupId": org_ownerid},
        )

    @segment_enabled
    def account_increased_users(self, current_user_ownerid, org_ownerid, plan_details):
        analytics.track(
            user_id=current_user_ownerid,
            event=SegmentEvent.ACCOUNT_INCREASED_USERS.value,
            properties=plan_details,
            context={"groupId": org_ownerid},
        )

    @segment_enabled
    def account_decreased_users(self, current_user_ownerid, org_ownerid, plan_details):
        analytics.track(
            user_id=current_user_ownerid,
            event=SegmentEvent.ACCOUNT_DECREASED_USERS.value,
            properties=plan_details,
            context={"groupId": org_ownerid},
        )

    @segment_enabled
    def account_paid_subscription(self, org_ownerid, stripe_subscription_details):
        analytics.track(
            user_id=BLANK_SEGMENT_USER_ID,
            event=SegmentEvent.ACCOUNT_PAID_SUBSCRIPTION.value,
            properties=stripe_subscription_details,
            context={"groupId": org_ownerid},
        )

    @segment_enabled
    def account_cancelled_subscription(self, org_ownerid, stripe_subscription_details):
        analytics.track(
            user_id=BLANK_SEGMENT_USER_ID,
            event=SegmentEvent.ACCOUNT_CANCELLED_SUBSCRIPTION.value,
            properties=stripe_subscription_details,
            context={"groupId": org_ownerid},
        )

    @segment_enabled
    def account_changed_plan(
        self, current_user_ownerid, org_ownerid, plan_change_details
    ):
        analytics.track(
            user_id=current_user_ownerid,
            event=SegmentEvent.ACCOUNT_CHANGED_PLAN.value,
            properties=plan_change_details,
            context={"groupId": org_ownerid},
        )

    @segment_enabled
    def account_completed_checkout(self, org_ownerid, checkout_session_details):
        analytics.track(
            user_id=BLANK_SEGMENT_USER_ID,
            event=SegmentEvent.ACCOUNT_COMPLETED_CHECKOUT.value,
            properties=checkout_session_details,
            context={"groupId": org_ownerid},
        )

    @segment_enabled
    def trial_started(self, org_ownerid, trial_details):
        analytics.track(
            user_id=BLANK_SEGMENT_USER_ID,
            event=SegmentEvent.TRIAL_STARTED.value,
            properties=trial_details,
            context={"groupId": org_ownerid},
        )

    @segment_enabled
    def trial_ended(self, org_ownerid, trial_details):
        analytics.track(
            user_id=BLANK_SEGMENT_USER_ID,
            event=SegmentEvent.TRIAL_ENDED.value,
            properties=trial_details,
            context={"groupId": org_ownerid},
        )

    @segment_enabled
    def account_installed_source_control_service_app(
        self, user_ownerid, org_ownerid, app_details
    ):
        analytics.track(
            user_id=user_ownerid,
            event=SegmentEvent.ACCOUNT_INSTALLED_SOURCE_CONTROL_APP.value,
            properties=app_details,
            context={"groupId": org_ownerid},
        )

    @segment_enabled
    def account_uninstalled_source_control_service_app(
        self, user_ownerid, org_ownerid, app_details
    ):
        analytics.track(
            user_id=org_ownerid,
            event=SegmentEvent.ACCOUNT_UNINSTALLED_SOURCE_CONTROL_APP.value,
            properties=app_details,
            context={"groupId": org_ownerid},
        )

    @segment_enabled
    def account_uploaded_coverage_report(self, org_ownerid, upload_details):
        analytics.track(
            user_id=BLANK_SEGMENT_USER_ID,
            event=SegmentEvent.ACCOUNT_UPLOADED_COVERAGE_REPORT.value,
            properties=upload_details,
            context={"groupId": org_ownerid},
        )
