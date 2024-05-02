from uuid import uuid4

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from codecov_auth.models import (
    DjangoSession,
    OktaUser,
    OrganizationLevelToken,
    Owner,
    OwnerProfile,
    RepositoryToken,
    SentryUser,
    Service,
    Session,
    TokenTypeChoices,
    User,
    UserToken,
)
from plan.constants import TrialStatus
from utils.encryption import encryptor


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Faker("email")
    name = factory.Faker("name")
    terms_agreement = False
    terms_agreement_at = None
    customer_intent = "Business"


class OwnerFactory(DjangoModelFactory):
    class Meta:
        model = Owner
        exclude = ("unencrypted_oauth_token",)

    name = factory.Faker("name")
    email = factory.Faker("email")
    username = factory.Faker("user_name")
    service = "github"
    service_id = factory.Sequence(lambda n: f"{n}")
    updatestamp = factory.LazyFunction(timezone.now)
    plan_activated_users = []
    admins = []
    permission = []
    free = 0
    onboarding_completed = False
    unencrypted_oauth_token = factory.LazyFunction(lambda: uuid4().hex)
    cache = {"stats": {"repos": 1, "members": 2, "users": 1}}
    oauth_token = factory.LazyAttribute(
        lambda o: encryptor.encode(o.unencrypted_oauth_token).decode()
    )
    user = factory.SubFactory(UserFactory)
    trial_status = TrialStatus.NOT_STARTED.value


class SentryUserFactory(DjangoModelFactory):
    class Meta:
        model = SentryUser

    email = factory.Faker("email")
    name = factory.Faker("name")
    sentry_id = factory.LazyFunction(lambda: uuid4().hex)
    access_token = factory.LazyFunction(lambda: uuid4().hex)
    refresh_token = factory.LazyFunction(lambda: uuid4().hex)
    user = factory.SubFactory(UserFactory)


class OktaUserFactory(DjangoModelFactory):
    class Meta:
        model = OktaUser

    email = factory.Faker("email")
    name = factory.Faker("name")
    okta_id = factory.LazyFunction(lambda: uuid4().hex)
    access_token = factory.LazyFunction(lambda: uuid4().hex)
    user = factory.SubFactory(UserFactory)


class OwnerProfileFactory(DjangoModelFactory):
    class Meta:
        model = OwnerProfile

    owner = factory.SubFactory(OwnerFactory)
    default_org = factory.SubFactory(OwnerFactory)


class DjangoSessionFactory(DjangoModelFactory):
    class Meta:
        model = DjangoSession

    expire_date = timezone.now()
    session_key = factory.Faker("uuid4")


class SessionFactory(DjangoModelFactory):
    class Meta:
        model = Session

    owner = factory.SubFactory(OwnerFactory)
    lastseen = timezone.now()
    type = Session.SessionType.API.value
    token = factory.Faker("uuid4")
    login_session = factory.SubFactory(DjangoSessionFactory)


class OrganizationLevelTokenFactory(DjangoModelFactory):
    class Meta:
        model = OrganizationLevelToken

    owner = factory.SubFactory(OwnerFactory)
    token = uuid4()
    token_type = TokenTypeChoices.UPLOAD


class GetAdminProviderAdapter:
    def __init__(self, result=False):
        self.result = result
        self.last_call_args = None

    async def get_is_admin(self, user):
        self.last_call_args = user
        return self.result


class UserTokenFactory(DjangoModelFactory):
    class Meta:
        model = UserToken

    owner = factory.SubFactory(OwnerFactory)
    token = factory.LazyAttribute(lambda _: uuid4())
