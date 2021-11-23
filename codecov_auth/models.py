import binascii
import logging
import os
import uuid
from datetime import datetime
from enum import Enum
from hashlib import md5

from django.contrib.postgres.fields import ArrayField, CITextField
from django.db import models

from billing.constants import BASIC_PLAN_NAME, USER_PLAN_REPRESENTATIONS
from codecov.models import BaseCodecovModel
from codecov_auth.constants import (
    AVATAR_GITHUB_BASE_URL,
    AVATARIO_BASE_URL,
    BITBUCKET_BASE_URL,
    GRAVATAR_BASE_URL,
)
from codecov_auth.helpers import get_gitlab_url
from core.managers import RepositoryQuerySet
from core.models import DateTimeWithoutTZField, Repository
from utils.config import get_config

from .managers import OwnerQuerySet

# Large number to represent Infinity as float('int') isnt JSON serializable
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


class Owner(models.Model):
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
    stripe_customer_id = models.TextField(null=True)
    stripe_subscription_id = models.TextField(null=True)

    # createstamp seems to be used by legacy to track first login
    # so we shouldn't touch this outside login
    createstamp = models.DateTimeField(null=True)

    service_id = models.TextField(null=False)
    parent_service_id = models.TextField(null=True)
    root_parent_service_id = models.TextField(null=True)
    private_access = models.BooleanField(null=True)
    staff = models.BooleanField(null=True, default=False)
    cache = models.JSONField(null=True)
    plan = models.TextField(null=True, default=BASIC_PLAN_NAME)  # Really an ENUM in db
    plan_provider = models.TextField(
        null=True, choices=PlanProviders.choices
    )  # postgres enum containing only "github"
    plan_user_count = models.SmallIntegerField(null=True, default=5)
    plan_auto_activate = models.BooleanField(null=True, default=True)
    plan_activated_users = ArrayField(models.IntegerField(null=True), null=True)
    did_trial = models.BooleanField(null=True)
    free = models.SmallIntegerField(default=0)
    invoice_details = models.TextField(null=True)
    delinquent = models.BooleanField(null=True)
    yaml = models.JSONField(null=True)
    updatestamp = DateTimeWithoutTZField(default=datetime.now)
    organizations = ArrayField(models.IntegerField(null=True), null=True)
    admins = ArrayField(models.IntegerField(null=True), null=True)
    integration_id = models.IntegerField(null=True)
    permission = ArrayField(models.IntegerField(null=True), null=True)
    bot = models.ForeignKey(
        "Owner", db_column="bot", null=True, on_delete=models.SET_NULL
    )
    student = models.BooleanField(default=False)
    student_created_at = DateTimeWithoutTZField(null=True)
    student_updated_at = DateTimeWithoutTZField(null=True)
    onboarding_completed = models.BooleanField(default=False)

    objects = OwnerQuerySet.as_manager()

    repository_set = RepositoryQuerySet.as_manager()

    def __str__(self):
        return f"Owner<{self.service}/{self.username}>"

    def save(self, *args, **kwargs):
        self.updatestamp = datetime.now()
        super().save(*args, **kwargs)

    @property
    def has_yaml(self):
        return self.yaml is not None

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

    def get_username(self):
        return self.username

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
        # Required to implement django's user-model interface for Django Admin
        return True

    @property
    def is_staff(self):
        # Required to implement django's user-model interface
        return self.staff

    def has_perm(self, perm, obj=None):
        # TODO : Implement real permissioning system
        # Required to implement django's user-model interface for Django Admin
        return self.is_staff

    def has_perms(self, *args, **kwargs):
        # TODO : Implement real permissioning system
        # Required to implement django's user-model interface
        return True

    def has_module_perms(self, package_name):
        # TODO : Implement real permissioning system
        # Required to implement django's user-model interface for Django Admin
        return self.is_staff

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
            plan_details = USER_PLAN_REPRESENTATIONS[self.plan].copy()

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

    def set_free_plan(self):
        log.info(f"Setting plan to users-free for owner {self.ownerid}")
        self.plan = "users-free"
        self.plan_activated_users = None
        self.plan_user_count = 5
        self.stripe_subscription_id = None
        self.save()


class OwnerProfile(BaseCodecovModel):
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


class Session(models.Model):
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
    type = models.TextField(choices=SessionType.choices)  # Really an ENUM in db


def _generate_key():
    return binascii.hexlify(os.urandom(20)).decode()


class RepositoryToken(BaseCodecovModel):
    repository = models.ForeignKey(
        "core.Repository",
        db_column="repoid",
        on_delete=models.CASCADE,
        related_name="tokens",
    )
    token_type = models.CharField(max_length=50)
    valid_until = models.DateTimeField(blank=True, null=True)
    key = models.CharField(
        max_length=40, unique=True, editable=False, default=_generate_key,
    )

    @classmethod
    def generate_key(cls):
        return _generate_key()
