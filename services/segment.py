import analytics
import re
from enum import Enum
from django.conf import settings
import logging


log = logging.getLogger(__name__)


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
    """
    def exec_method(*args, **kwargs):
        if settings.SEGMENT_ENABLED:
            return method(*args, **kwargs)
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


class SegmentEvent(Enum):
    ACCOUNT_ACTIVATED_REPOSITORY_ON_UPLOAD = 'Account Activated Repository On Upload'
    ACCOUNT_ACTIVATED_REPOSITORY = 'Account Activated Repository'
    ACCOUNT_ACTIVATED_USER = 'Account Activated User'
    ACCOUNT_ADDED_USER = 'Account Added User' # TODO: check with Jon how this is different from Account Activated User?
    ACCOUNT_CANCELLED_SUBSCRIPTION = 'Account Cancelled Subscription'
    ACCOUNT_CHANGED_PLAN = 'Account Changed Plan'
    ACCOUNT_COMPLETED_CHECKOUT = 'Account Completed Checkout'
    ACCOUNT_CREATED = 'Account Created'
    ACCOUNT_DEACTIVATED_REPOSITORY = 'Account Deactivated Repository'
    ACCOUNT_DEACTIVATED_USER = 'Account Deactivated User'
    ACCOUNT_DECREASED_USERS = 'Account Decreased Users'
    ACCOUNT_DELETED_REPOSITORY = 'Account Deleted Repository'
    ACCOUNT_DELETED = 'Account Deleted'
    ACCOUNT_ERASED_REPOSITIROY = 'Account Erased Repository'
    ACCOUNT_INCREASED_USERS = 'Account Increased Users'
    ACCOUNT_INSTALLED_SOURCE_CONTROL_APP = 'Account Installed Source Control Service App'
    ACCOUNT_PAID_SUBSCRIPTION = 'Account Paid Subscription'
    ACCOUNT_REMOVED_USER = 'Account Removed User' # TODO: check with Jon how this is different from Account Deactivated User?
    ACCOUNT_UNISTALLED_SOURCE_CONTROL_APP = 'Account Uninstalled Source Control Service App'
    ACCOUNT_UPLOADED_COVERAGE_REPORT = 'Account Uploaded Coverage Report'
    TRIAL_ENDED = 'Trial Ended'
    TRIAL_STARTED = 'Trial Started'
    USER_SIGNED_IN = 'User Signed In'
    USER_SIGNED_OUT = 'User Signed Out'
    USER_SIGNED_UP = 'User Signed Up'


class SegmentOwner:
    """
    An object wrapper around 'Owner' that provides "user_id", "traits",
    and "context" properties.
    """

    def __init__(self, owner, cookies={}):
        self.owner = owner
        self.cookies = cookies

    @property
    def user_id(self):
        return self.owner.ownerid

    @property
    def traits(self):
        return {
            'email': self.owner.email, 
            'name': self.owner.name,
            'username': self.owner.username,
            'avatar': self.owner.avatar_url,
            'createdAt': self.owner.createstamp,
            'updatedAt': self.owner.updatestamp,
            'service': self.owner.service,
            'service_id': self.owner.service_id,
            'private_access': self.owner.private_access,
            'plan': self.owner.plan,
            'plan_provider': self.owner.plan_provider,
            'plan_user_count': self.owner.plan_user_count,
            'delinquent': self.owner.delinquent,
            'did_trial': self.owner.did_trial,
            'student': self.owner.student,
            'student_created_at': self.owner.student_created_at,
            'student_updated_at': self.owner.student_updated_at,
            'staff': self.owner.staff,
            'bot': self.owner.bot,
            'has_yaml': self.owner.yaml is not None,
        }

    @property
    def context(self):
        """
            Mostly copied from
            https://github.com/codecov/codecov.io/blob/master/app/services/analytics_tracking.py#L107
        """
        context = {"externalIds": []}

        context["externalIds"].append({
            "id": self.owner.service_id,
            "type": f"{self.owner.service}_id",
            "collection": "users",
            "encoding": "none"
        })

        if self.owner.stripe_customer_id:
            context["externalIds"].append({
                "id": self.owner.stripe_customer_id,
                "type": "stripe_customer_id",
                "collection": "users",
                "encoding": "none"
            })

        if self.cookies:
            marketo_cookie = self.cookies.get("_mkto_trk")
            ga_cookie = self.cookies.get("_ga")
            if marketo_cookie:
                context["externalIds"].append({
                    "id": marketo_cookie,
                    "type": "marketo_cookie",
                    "collection": "users",
                    "encoding": "none"
                })
                context["Marketo"] = {"marketo_cookie": marketo_cookie}
            if ga_cookie:
                # id is everything after the "GA.1." prefix
                match = re.match('^.+\.(.+?\..+?)$', ga_cookie)
                if match:
                    ga_client_id = match.group(1)
                    context["externalIds"].append({
                        "id": ga_client_id,
                        "type": "ga_client_id",
                        "collection": "users",
                        "encoding": "none"
                    })

        return context


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
            integrations={
                "Salesforce": False,
                "Marketo": False
            }
        )

    @inject_segment_owner
    def user_signed_up(self, segment_owner):
        analytics.track(
            segment_owner.user_id,
            SegmentEvent.USER_SIGNED_UP.value,
            segment_owner.traits
        )

    @inject_segment_owner
    def user_signed_in(self, segment_owner):
        analytics.track(
            segment_owner.user_id,
            SegmentEvent.USER_SIGNED_IN.value,
            segment_owner.traits
        )

    @inject_segment_owner
    def user_signed_out(self, segment_owner):
        analytics.track(
            segment_owner.user_id,
            SegmentEvent.USER_SIGNED_OUT.value,
            segment_owner.traits
        )

    @segment_enabled
    def account_activated_user(self, current_user_ownerid, ownerid_to_activate, org_ownerid, auto_activated=False):
        analytics.track(
            user_id=current_user_ownerid,
            event=SegmentEvent.ACCOUNT_ACTIVATED_USER.value,
            properties={
                "role": "admin",
                "user": ownerid_to_activate,
                "auto_activated": auto_activated
            },
            context={"groupId": org_ownerid}
        )

    @segment_enabled
    def account_deactivated_user(self, current_user_ownerid, ownerid_to_deactivate, org_ownerid):
        analytics.track(
            user_id=current_user_ownerid,
            event=SegmentEvent.ACCOUNT_DEACTIVATED_USER.value,
            properties={
                "role": "admin",
                "user": ownerid_to_deactivate,
            },
            context={"groupId": org_ownerid}
        )

    @segment_enabled
    def account_increased_users(self, org_ownerid, plan_details):
        analytics.track(
            user_id=org_ownerid,
            event=SegmentEvent.ACCOUNT_INCREASED_USERS.value,
            properties=plan_details,
            context={"groupId": org_ownerid}
        )

    @segment_enabled
    def account_decreased_users(self, org_ownerid, plan_details):
        analytics.track(
            user_id=org_ownerid,
            event=SegmentEvent.ACCOUNT_DECREASED_USERS.value,
            properties=plan_details,
            context={"groupId": org_ownerid}
        )
