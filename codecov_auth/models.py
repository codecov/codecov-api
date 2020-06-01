import os
import uuid
import logging
from time import time
from hashlib import md5
from enum import Enum

from django.db import models
from core.models import Repository
from utils.config import get_config
from django.contrib.postgres.fields import CITextField, JSONField, ArrayField

from codecov_auth.constants import (
    AVATAR_GITHUB_BASE_URL,
    BITBUCKET_BASE_URL,
    GRAVATAR_BASE_URL,
    AVATARIO_BASE_URL,
)

from codecov_auth.helpers import get_gitlab_url

SERVICE_GITHUB = 'github'
SERVICE_GITHUB_ENTERPRISE = 'github_enterprise'
SERVICE_BITBUCKET = 'bitbucket'
SERVICE_BITBUCKET_SERVER = 'bitbucket_server'
SERVICE_GITLAB = 'gitlab'
SERVICE_CODECOV_ENTERPRISE = 'enterprise'

DEFAULT_AVATAR_SIZE = 55

log = logging.getLogger(__name__)


# TODO use this to refactor avatar_url
class Service(Enum):
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    GITHUB_ENTERPRISE = "github_enterprise"
    GITLAB_ENTERPRISE = "gitlab_enterprise"
    BITBUCKET_SERVER = "bitbucket_server"


class Owner(models.Model):

    class Meta:
        db_table = 'owners'

    REQUIRED_FIELDS = []
    USERNAME_FIELD = 'username'

    ownerid = models.AutoField(primary_key=True)
    service = models.CharField(max_length=256)
    username = CITextField(null=True, unique=True)
    email = models.TextField(null=True)
    name = models.TextField(null=True)
    oauth_token = models.TextField(null=True)
    stripe_customer_id = models.TextField(null=True)
    stripe_subscription_id = models.TextField(null=True)
    createstamp = models.DateTimeField(auto_now_add=True)
    service_id = models.TextField()
    private_access = models.BooleanField(null=True)
    staff = models.BooleanField(null=True, default=False)
    cache = JSONField(null=True)
    plan = models.TextField(null=True)
    # plan_provider
    plan_user_count = models.SmallIntegerField(null=True)
    plan_auto_activate = models.BooleanField(null=True)
    plan_activated_users = ArrayField(models.IntegerField(null=True), null=True)
    did_trial = models.BooleanField(null=True)
    free = models.SmallIntegerField(default=0)
    invoice_details = models.TextField(null=True)
    delinquent = models.BooleanField(null=True)
    yaml = JSONField(null=True)
    updatestamp = models.DateTimeField(auto_now=True)
    organizations = ArrayField(models.IntegerField(null=True), null=True)
    admins = ArrayField(models.IntegerField(null=True), null=True)
    integration_id = models.IntegerField(null=True)
    permission = ArrayField(models.IntegerField(null=True), null=True)
    bot = models.IntegerField(null=True)
    student = models.BooleanField(default=False)

    @property
    def has_legacy_plan(self):
        return self.plan is None or not self.plan.startswith('users')

    @property
    def repo_credits(self):
        # Returns the number of private repo credits remaining
        # Only meaningful for legacy plans
        V4_PLAN_PREFIX = 'v4-'

        if not self.has_legacy_plan:
            return float('inf')
        if self.plan is None:
            repos = 1 + self.free or 0
        elif self.plan.startswith(V4_PLAN_PREFIX):
            repos = self.plan[3:-1]
        else:
            repos = self.plan[:-1]
        return int(repos) - self.repository_set.filter(active=True, private=True).count()

    @property
    def orgs(self):
        if self.organizations:
            return Owner.objects.filter(ownerid__in=self.organizations)
        return Owner.objects.none()

    @property
    def active_repos(self):
        return Repository.objects.filter(
            active=True,
            author=self.ownerid
        ).order_by('-updatestamp')

    @property
    def activated_user_count(self):
        if not self.plan_activated_users:
            return 0
        return Owner.objects.filter(ownerid__in=self.plan_activated_users, student=False).count()

    @property
    def inactive_user_count(self):
        return Owner.objects.filter(
            organizations__contains=[self.ownerid]
        ).count() - self.activated_user_count

    def is_admin(self, owner):
        return self.ownerid == owner.ownerid or (bool(self.admins) and owner.ownerid in self.admins)

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

    def has_perms(self, *args, **kwargs):
        # TODO : Implement real permissioning system
        # Required to implement django's user-model interface
        return True

    @property
    def avatar_url(self, size=DEFAULT_AVATAR_SIZE):
        if self.service == SERVICE_GITHUB and self.service_id:
            return '{}/u/{}?v=3&s={}'.format(AVATAR_GITHUB_BASE_URL, self.service_id, size)

        elif self.service == SERVICE_GITHUB_ENTERPRISE and self.service_id:
            return '{}/avatars/u/{}?v=3&s={}'.format(get_config('github_enterprise', 'url'), self.service_id, size)

        # Bitbucket
        elif self.service == SERVICE_BITBUCKET and self.username:
            return '{}/account/{}/avatar/{}'.format(BITBUCKET_BASE_URL, self.username, size)

        elif self.service == SERVICE_BITBUCKET_SERVER and self.service_id and self.username:
            if 'U' in self.service_id:
                return '{}/users/{}/avatar.png?s={}'.format(get_config('bitbucket_server', 'url'), self.username, size)
            else:
                return '{}/projects/{}/avatar.png?s={}'.format(get_config('bitbucket_server', 'url'), self.username, size)

        # Gitlab
        elif self.service == SERVICE_GITLAB and self.email:
            return get_gitlab_url(self.email, size)

        # Codecov config
        elif get_config('services', 'gravatar') and self.email:
            return '{}/avatar/{}?s={}'.format(GRAVATAR_BASE_URL, md5(self.email.lower().encode()).hexdigest(), size)

        elif get_config('services', 'avatars.io') and self.email:
            return '{}/avatar/{}/{}'.format(AVATARIO_BASE_URL, md5(self.email.lower().encode()).hexdigest(), size)

        elif self.ownerid:
            return '{}/users/{}.png?size={}'.format(get_config('setup', 'codecov_url'), self.ownerid, size)

        elif os.getenv('APP_ENV') == SERVICE_CODECOV_ENTERPRISE:
            return '{}/media/images/gafsi/avatar.svg'.format(get_config('setup', 'codecov_url'))

        else:
            return '{}/media/images/gafsi/avatar.svg'.format(get_config('setup', 'media', 'assets'))

    def can_activate_user(self, user):
        return user.student or self.activated_user_count < self.plan_user_count + self.free

    def activate_user(self, user):
        if isinstance(self.plan_activated_users, list):
            if user.ownerid not in self.plan_activated_users:
                self.plan_activated_users.append(user.ownerid)
        else:
            self.plan_activated_users = [user.ownerid]
        self.save()

    def deactivate_user(self, user):
        if isinstance(self.plan_activated_users, list):
            try:
                self.plan_activated_users.remove(user.ownerid)
            except ValueError:
                pass
        self.save()

    def add_admin(self, user):
        if isinstance(self.admins, list):
            if user.ownerid not in self.admins:
                self.admins.append(user.ownerid)
        else:
            self.admins = [user.ownerid]
        self.save()

    def remove_admin(self, user):
        if isinstance(self.admins, list):
            try:
                self.admins.remove(user.ownerid)
            except ValueError:
                pass
        self.save()


class Session(models.Model):

    class Meta:
        db_table = 'sessions'

    sessionid = models.AutoField(primary_key=True)
    token = models.UUIDField(default=uuid.uuid4, editable=False)
    name = models.TextField()
    useragent = models.TextField()
    ip = models.TextField()
    owner = models.ForeignKey(
        Owner, db_column='ownerid', on_delete=models.CASCADE)
    lastseen = models.DateTimeField()
    # type
