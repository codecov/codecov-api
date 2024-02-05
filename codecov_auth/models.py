import binascii
import logging
import os
import uuid
from dataclasses import asdict
from datetime import datetime
from hashlib import md5

from django.contrib.postgres.fields import ArrayField, CITextField
from django.db import models
from django.db.models.manager import BaseManager
from django.forms import ValidationError
from django.utils import timezone
from django_prometheus.models import ExportModelOperationsMixin

from codecov.models import BaseCodecovModel
from codecov_auth.constants import (
    AVATAR_GITHUB_BASE_URL,
    AVATARIO_BASE_URL,
    BITBUCKET_BASE_URL,
    GRAVATAR_BASE_URL,
)
from codecov_auth.helpers import get_gitlab_url
from core.managers import RepositoryManager
from core.models import DateTimeWithoutTZField, Repository
from plan.constants import USER_PLAN_REPRESENTATIONS, PlanName
from utils.config import get_config

from .managers import OwnerManager

# Large number to represent Infinity as float('int') is not JSON serializable
INFINITY = 99999999

SERVICE_GITHUB = "github"
SERVICE_GITHUB_ENTERPRISE = "github_enterprise"
SERVICE_BITBUCKET = "bitbucket"
SERVICE_BITBUCKET_SERVER = "bitbucket_server"
SERVICE_GITLAB = "gitlab"
SERVICE_CODECOV_ENTERPRISE = "enterprise"


DEFAULT_AVATAR_SIZE = 55


log = logging.getLogger(__name__)


# TODO use this to refactor avatar_url
class Service(models.TextChoices):
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    GITHUB_ENTERPRISE = "github_enterprise"
    GITLAB_ENTERPRISE = "gitlab_enterprise"
    BITBUCKET_SERVER = "bitbucket_server"


class PlanProviders(models.TextChoices):
    GITHUB = "github"


# Follow the shape of TrialStatus in plan folder
class TrialStatus(models.TextChoices):
    NOT_STARTED = "not_started"
    ONGOING = "ongoing"
    EXPIRED = "expired"
    CANNOT_TRIAL = "cannot_trial"


class User(ExportModelOperationsMixin("codecov_auth.user"), BaseCodecovModel):
    email = CITextField(null=True)
    name = models.TextField(null=True)
    is_staff = models.BooleanField(null=True, default=False)
    is_superuser = models.BooleanField(null=True, default=False)
    external_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    terms_agreement = models.BooleanField(null=True, default=False, blank=True)
    terms_agreement_at = DateTimeWithoutTZField(null=True, blank=True)

    REQUIRED_FIELDS = []
    USERNAME_FIELD = "external_id"

    class Meta:
        db_table = "users"

    @property
    def is_active(self):
        # Required to implement django's user-model interface
        return True

    @property
    def is_anonymous(self):
        # Required to implement django's user-model interface
        return False

    @property
    def is_authenticated(self):
        # Required to implement django's user-model interface
        return True

    def has_perm(self, perm, obj=None):
        # Required to implement django's user-model interface
        return self.is_staff

    def has_perms(self, *args, **kwargs):
        # Required to implement django's user-model interface
        return self.is_staff

    def has_module_perms(self, package_name):
        # Required to implement django's user-model interface
        return self.is_staff

    def get_username(self):
        # Required to implement django's user-model interface
        return self.external_id


class Owner(ExportModelOperationsMixin("codecov_auth.owner"), models.Model):
    class Meta:
        db_table = "owners"
        ordering = ["ownerid"]
        constraints = [
            models.UniqueConstraint(
                fields=["service", "username"], name="owner_service_username"
            ),
            models.UniqueConstraint(
                fields=["service", "service_id"], name="owner_service_ids"
            ),
        ]

    REQUIRED_FIELDS = []
    USERNAME_FIELD = "username"

    ownerid = models.AutoField(primary_key=True)
    service = models.TextField(choices=Service.choices)  # Really an ENUM in db
    username = CITextField(
        unique=True, null=True
    )  # No actual unique constraint on this in the DB
    email = models.TextField(null=True)
    business_email = models.TextField(null=True)
    name = models.TextField(null=True)
    oauth_token = models.TextField(null=True)
    stripe_customer_id = models.TextField(null=True, blank=True)
    stripe_subscription_id = models.TextField(null=True, blank=True)
    stripe_coupon_id = models.TextField(null=True, blank=True)

    # createstamp seems to be used by legacy to track first login
    # so we shouldn't touch this outside login
    createstamp = models.DateTimeField(null=True)

    service_id = models.TextField(null=False)
    parent_service_id = models.TextField(null=True)
    root_parent_service_id = models.TextField(null=True)
    private_access = models.BooleanField(null=True)
    staff = models.BooleanField(null=True, default=False)
    cache = models.JSONField(null=True)
    # Really an ENUM in db
    plan = models.TextField(
        null=True, default=PlanName.BASIC_PLAN_NAME.value, blank=True
    )
    plan_provider = models.TextField(
        null=True, choices=PlanProviders.choices, blank=True
    )  # postgres enum containing only "github"
    plan_user_count = models.SmallIntegerField(null=True, default=1, blank=True)
    plan_auto_activate = models.BooleanField(null=True, default=True)
    plan_activated_users = ArrayField(
        models.IntegerField(null=True), null=True, blank=True
    )
    did_trial = models.BooleanField(null=True)
    trial_start_date = DateTimeWithoutTZField(null=True)
    trial_end_date = DateTimeWithoutTZField(null=True)
    trial_status = models.CharField(
        max_length=50,
        choices=TrialStatus.choices,
        null=True,
        default=TrialStatus.NOT_STARTED.value,
    )
    trial_fired_by = models.IntegerField(null=True)
    pretrial_users_count = models.SmallIntegerField(null=True, blank=True)
    free = models.SmallIntegerField(default=0)
    invoice_details = models.TextField(null=True)
    uses_invoice = models.BooleanField(default=False, null=False)
    delinquent = models.BooleanField(null=True)
    yaml = models.JSONField(null=True)
    updatestamp = DateTimeWithoutTZField(default=datetime.now)
    organizations = ArrayField(models.IntegerField(null=True), null=True, blank=True)
    admins = ArrayField(models.IntegerField(null=True), null=True, blank=True)

    # DEPRECATED - replaced by GithubAppInstallation model
    integration_id = models.IntegerField(null=True, blank=True)

    permission = ArrayField(models.IntegerField(null=True), null=True)
    bot = models.ForeignKey(
        "Owner", db_column="bot", null=True, on_delete=models.SET_NULL, blank=True
    )
    student = models.BooleanField(default=False)
    student_created_at = DateTimeWithoutTZField(null=True)
    student_updated_at = DateTimeWithoutTZField(null=True)
    onboarding_completed = models.BooleanField(default=False)
    is_superuser = models.BooleanField(null=True, default=False)
    max_upload_limit = models.IntegerField(null=True, default=150, blank=True)

    sentry_user_id = models.TextField(null=True, blank=True, unique=True)
    sentry_user_data = models.JSONField(null=True)

    user = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        blank=True,
        related_name="owners",
    )

    objects = OwnerManager()

    repository_set = RepositoryManager()

    def __str__(self):
        return f"Owner<{self.service}/{self.username}>"

    def save(self, *args, **kwargs):
        self.updatestamp = timezone.now()
        super().save(*args, **kwargs)

    @property
    def has_yaml(self):
        return self.yaml is not None

    @property
    def default_org(self):
        try:
            if self.profile:
                return self.profile.default_org
        except OwnerProfile.DoesNotExist:
            return None

    @property
    def has_legacy_plan(self):
        return self.plan is None or not self.plan.startswith("users")

    @property
    def repo_total_credits(self):
        # Returns the number of private repo credits remaining
        # Only meaningful for legacy plans
        V4_PLAN_PREFIX = "v4-"
        if not self.has_legacy_plan:
            return INFINITY
        if self.plan is None:
            return int(1 + self.free or 0)
        elif self.plan.startswith(V4_PLAN_PREFIX):
            return int(self.plan[3:-1])
        else:
            return int(self.plan[:-1])

    @property
    def root_organization(self):
        """
        Find the root organization of Gitlab, by using the root_parent_service_id
        if it exists, otherwise iterating through the parents and caches it in root_parent_service_id
        """
        if self.root_parent_service_id:
            return Owner.objects.get(
                service_id=self.root_parent_service_id, service=self.service
            )

        root = None
        if self.service == "gitlab" and self.parent_service_id:
            root = self
            while root.parent_service_id is not None:
                root = Owner.objects.get(
                    service_id=root.parent_service_id, service=root.service
                )
            self.root_parent_service_id = root.service_id
            self.save()
        return root

    @property
    def nb_active_private_repos(self):
        return self.repository_set.filter(active=True, private=True).count()

    @property
    def has_private_repos(self):
        return self.repository_set.filter(private=True).exists()

    @property
    def repo_credits(self):
        # Returns the number of private repo credits remaining
        # Only meaningful for legacy plans
        if not self.has_legacy_plan:
            return INFINITY
        return self.repo_total_credits - self.nb_active_private_repos

    @property
    def orgs(self):
        if self.organizations:
            return Owner.objects.filter(ownerid__in=self.organizations)
        return Owner.objects.none()

    @property
    def active_repos(self):
        return Repository.objects.filter(active=True, author=self.ownerid).order_by(
            "-updatestamp"
        )

    @property
    def activated_user_count(self):
        if not self.plan_activated_users:
            return 0
        return Owner.objects.filter(
            ownerid__in=self.plan_activated_users, student=False
        ).count()

    @property
    def activated_student_count(self):
        if not self.plan_activated_users:
            return 0
        return Owner.objects.filter(
            ownerid__in=self.plan_activated_users, student=True
        ).count()

    @property
    def student_count(self):
        return Owner.objects.users_of(self).filter(student=True).count()

    @property
    def inactive_user_count(self):
        return (
            Owner.objects.users_of(self).filter(student=False).count()
            - self.activated_user_count
        )

    def is_admin(self, owner):
        return self.ownerid == owner.ownerid or (
            bool(self.admins) and owner.ownerid in self.admins
        )

    @property
    def is_authenticated(self):
        # NOTE: this is here to support `UserTokenAuthentication` which still returns
        # an `Owner` as the authenticatable record.  Since there is code that calls
        # `request.user.is_authenticated` we need to support that here.
        return True

    def clean(self):
        if self.staff:
            domain = self.email.split("@")[1] if self.email else ""
            if domain not in ["codecov.io", "sentry.io"]:
                raise ValidationError(
                    "User not part of Codecov or Sentry cannot be a staff member"
                )
        if not self.plan:
            self.plan = None
        if not self.stripe_customer_id:
            self.stripe_customer_id = None
        if not self.stripe_subscription_id:
            self.stripe_subscription_id = None

    @property
    def avatar_url(self, size=DEFAULT_AVATAR_SIZE):
        if self.service == SERVICE_GITHUB and self.service_id:
            return "{}/u/{}?v=3&s={}".format(
                AVATAR_GITHUB_BASE_URL, self.service_id, size
            )

        elif self.service == SERVICE_GITHUB_ENTERPRISE and self.service_id:
            return "{}/avatars/u/{}?v=3&s={}".format(
                get_config("github_enterprise", "url"), self.service_id, size
            )

        # Bitbucket
        elif self.service == SERVICE_BITBUCKET and self.username:
            return "{}/account/{}/avatar/{}".format(
                BITBUCKET_BASE_URL, self.username, size
            )

        elif (
            self.service == SERVICE_BITBUCKET_SERVER
            and self.service_id
            and self.username
        ):
            if "U" in self.service_id:
                return "{}/users/{}/avatar.png?s={}".format(
                    get_config("bitbucket_server", "url"), self.username, size
                )
            else:
                return "{}/projects/{}/avatar.png?s={}".format(
                    get_config("bitbucket_server", "url"), self.username, size
                )

        # Gitlab
        elif self.service == SERVICE_GITLAB and self.email:
            return get_gitlab_url(self.email, size)

        # Codecov config
        elif get_config("services", "gravatar") and self.email:
            return "{}/avatar/{}?s={}".format(
                GRAVATAR_BASE_URL, md5(self.email.lower().encode()).hexdigest(), size
            )

        elif get_config("services", "avatars.io") and self.email:
            return "{}/avatar/{}/{}".format(
                AVATARIO_BASE_URL, md5(self.email.lower().encode()).hexdigest(), size
            )

        elif self.ownerid:
            return "{}/users/{}.png?size={}".format(
                get_config("setup", "codecov_url"), self.ownerid, size
            )

        elif os.getenv("APP_ENV") == SERVICE_CODECOV_ENTERPRISE:
            return "{}/media/images/gafsi/avatar.svg".format(
                get_config("setup", "codecov_url")
            )

        else:
            return "{}/media/images/gafsi/avatar.svg".format(
                get_config("setup", "media", "assets")
            )

    @property
    def pretty_plan(self):
        if self.plan in USER_PLAN_REPRESENTATIONS:
            plan_details = asdict(USER_PLAN_REPRESENTATIONS[self.plan])

            # update with quantity they've purchased
            # allows api users to update the quantity
            # by modifying the "plan", sidestepping
            # some iffy data modeling

            plan_details.update({"quantity": self.plan_user_count})
            return plan_details

    def can_activate_user(self, user):
        return (
            user.student or self.activated_user_count < self.plan_user_count + self.free
        )

    def activate_user(self, user):
        log.info(f"Activating user {user.ownerid} in ownerid {self.ownerid}")
        if isinstance(self.plan_activated_users, list):
            if user.ownerid not in self.plan_activated_users:
                self.plan_activated_users.append(user.ownerid)
        else:
            self.plan_activated_users = [user.ownerid]
        self.save()

    def deactivate_user(self, user):
        log.info(f"Deactivating user {user.ownerid} in ownerid {self.ownerid}")
        if isinstance(self.plan_activated_users, list):
            try:
                self.plan_activated_users.remove(user.ownerid)
            except ValueError:
                pass
        self.save()

    def add_admin(self, user):
        log.info(
            f"Granting admin permissions to user {user.ownerid} within owner {self.ownerid}"
        )
        if isinstance(self.admins, list):
            if user.ownerid not in self.admins:
                self.admins.append(user.ownerid)
        else:
            self.admins = [user.ownerid]
        self.save()

    def remove_admin(self, user):
        log.info(
            f"Revoking admin permissions for user {user.ownerid} within owner {self.ownerid}"
        )
        if isinstance(self.admins, list):
            try:
                self.admins.remove(user.ownerid)
            except ValueError:
                pass
        self.save()


GITHUB_APP_INSTALLATION_DEFAULT_NAME = "codecov_app_installation"


class GithubAppInstallation(
    ExportModelOperationsMixin("codecov_auth.github_app_installation"), BaseCodecovModel
):

    # replacement for owner.integration_id
    # installation id GitHub sends us in the installation-related webhook events
    installation_id = models.IntegerField(null=False, blank=False)
    name = models.TextField(default=GITHUB_APP_INSTALLATION_DEFAULT_NAME)
    # if null, all repos are covered by this installation
    # otherwise, it's a list of repo.id values
    repository_service_ids = ArrayField(models.TextField(null=False), null=True)

    owner = models.ForeignKey(
        Owner,
        null=False,
        on_delete=models.CASCADE,
        blank=False,
        related_name="github_app_installations",
    )

    def repository_queryset(self) -> BaseManager[Repository]:
        """Returns a QuerySet of repositories covered by this installation"""
        if self.repository_service_ids is None:
            # All repos covered
            return Repository.objects.filter(author=self.owner)
        # Some repos covered
        return Repository.objects.filter(
            service_id__in=self.repository_service_ids, author=self.owner
        )

    def covers_all_repos(self) -> bool:
        return self.repository_service_ids is None

    def is_repo_covered_by_integration(self, repo: Repository) -> bool:
        if self.covers_all_repos():
            return repo.author.ownerid == self.owner.ownerid
        return repo.service_id in self.repository_service_ids


class SentryUser(
    ExportModelOperationsMixin("codecov_auth.sentry_user"), BaseCodecovModel
):
    user = models.ForeignKey(
        User,
        null=False,
        on_delete=models.CASCADE,
        related_name="sentry_user",
    )
    access_token = models.TextField(null=True)
    refresh_token = models.TextField(null=True)
    sentry_id = models.TextField(null=False, unique=True)
    email = models.TextField(null=True)
    name = models.TextField(null=True)


class OktaUser(ExportModelOperationsMixin("codecov_auth.okta_user"), BaseCodecovModel):
    user = models.ForeignKey(
        User,
        null=False,
        on_delete=models.CASCADE,
        related_name="okta_user",
    )
    access_token = models.TextField(null=True)
    okta_id = models.TextField(null=False, unique=True)
    email = models.TextField(null=True)
    name = models.TextField(null=True)


class TokenTypeChoices(models.TextChoices):
    UPLOAD = "upload"


class OrganizationLevelToken(
    ExportModelOperationsMixin("codecov_auth.organization_level_token"),
    BaseCodecovModel,
):
    owner = models.ForeignKey(
        "Owner",
        db_column="ownerid",
        related_name="organization_tokens",
        on_delete=models.CASCADE,
    )
    token = models.UUIDField(unique=True, default=uuid.uuid4)
    valid_until = models.DateTimeField(blank=True, null=True)
    token_type = models.CharField(
        max_length=50, choices=TokenTypeChoices.choices, default=TokenTypeChoices.UPLOAD
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class OwnerProfile(
    ExportModelOperationsMixin("codecov_auth.owner_profile"), BaseCodecovModel
):
    class ProjectType(models.TextChoices):
        PERSONAL = "PERSONAL"
        YOUR_ORG = "YOUR_ORG"
        OPEN_SOURCE = "OPEN_SOURCE"
        EDUCATIONAL = "EDUCATIONAL"

    class Goal(models.TextChoices):
        STARTING_WITH_TESTS = "STARTING_WITH_TESTS"
        IMPROVE_COVERAGE = "IMPROVE_COVERAGE"
        MAINTAIN_COVERAGE = "MAINTAIN_COVERAGE"
        TEAM_REQUIREMENTS = "TEAM_REQUIREMENTS"
        OTHER = "OTHER"

    owner = models.OneToOneField(
        Owner, on_delete=models.CASCADE, unique=True, related_name="profile"
    )
    type_projects = ArrayField(
        models.TextField(choices=ProjectType.choices), default=list
    )
    goals = ArrayField(models.TextField(choices=Goal.choices), default=list)
    other_goal = models.TextField(null=True)
    default_org = models.ForeignKey(
        Owner, on_delete=models.CASCADE, null=True, related_name="profiles_with_default"
    )


class Session(ExportModelOperationsMixin("codecov_auth.session"), models.Model):
    class Meta:
        db_table = "sessions"
        ordering = ["-lastseen"]

    class SessionType(models.TextChoices):
        API = "api"
        LOGIN = "login"

    sessionid = models.AutoField(primary_key=True)
    token = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    name = models.TextField(null=True)
    useragent = models.TextField(null=True)
    ip = models.TextField(null=True)
    owner = models.ForeignKey(Owner, db_column="ownerid", on_delete=models.CASCADE)
    lastseen = models.DateTimeField(null=True)
    # Really an ENUM in db
    type = models.TextField(choices=SessionType.choices)


def _generate_key():
    return binascii.hexlify(os.urandom(20)).decode()


class RepositoryToken(
    ExportModelOperationsMixin("codecov_auth.repository_token"), BaseCodecovModel
):
    class TokenType(models.TextChoices):
        UPLOAD = "upload"
        PROFILING = "profiling"
        STATIC_ANALYSIS = "static_analysis"

    repository = models.ForeignKey(
        "core.Repository",
        db_column="repoid",
        on_delete=models.CASCADE,
        related_name="tokens",
    )
    token_type = models.CharField(max_length=50, choices=TokenType.choices)
    valid_until = models.DateTimeField(blank=True, null=True)
    key = models.CharField(
        max_length=40, unique=True, editable=False, default=_generate_key
    )

    @classmethod
    def generate_key(cls):
        return _generate_key()


class UserToken(
    ExportModelOperationsMixin("codecov_auth.user_token"), BaseCodecovModel
):
    class TokenType(models.TextChoices):
        API = "api"

    name = models.CharField(max_length=100, null=False, blank=False)
    owner = models.ForeignKey(
        "Owner",
        db_column="ownerid",
        related_name="user_tokens",
        on_delete=models.CASCADE,
    )
    token = models.UUIDField(unique=True, default=uuid.uuid4)
    valid_until = models.DateTimeField(blank=True, null=True)
    token_type = models.CharField(
        max_length=50, choices=TokenType.choices, default=TokenType.API
    )
