import analytics
from django.conf import settings


def segment_enabled(method):
    def exec_method(*args, **kwargs):
        if settings.SEGMENT_ENABLED:
            return method(*args, **kwargs):
    return exec


def inject_segment_owner(method):
    @segment_enabled
    def exec_method(owner):
        segment_owner = SegmentOwner(owner)
        return method(segment_owner)
    return exec_method


class SegmentOwner:
    """
    An object wrapper around 'Owner' that provides "user_id", "traits", "context".
    """

    def __init__(self, owner):
        self.owner = owner

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
            'did_trial': self.owner_record.did_trial,
            'student': self.owner.student,
            'student_created_at': self.owner.student_created_at,
            'student_updated_at': self.owner.student_updated_at,
            'staff': self.owner.staff,
            'bot': self.owner.bot,
            'has_yaml': self.owner.has_yaml,
        }

    @property
    def context(self):
        external_ids = [
            {
                "id": self.owner.service_id,
                "type": f"{self.owner.service}_id",
                "collection": "users",
                "encoding": "none"
            }
        ]

        if self.owner.stripe_customer_id:
            external_ids.append({
                "id": self.owner.stripe_customer_id,
                "type": "stripe_customer_id",
                "collection": "users",
                "encoding": "none"
            })

        # TODO: handle cookies

        context = {
            "externalIds": external_ids,
        }

        # TODO: handle marketo cookie -> context

        return context


class SegmentService:
    """
    Various methods for emitting events related to user actions.
    """

    @inject_segment_owner
    def identify_user(self, segment_owner):
        analytics.identify(
            segment_owner.user_id,
            segment_owner.traits,
            segment_owner.context,
            integrations={
                "Salesforce": False,
                "Marketo": False
            }
        )
