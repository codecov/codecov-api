import uuid
import logging

from django.db import models
from django.contrib.postgres.fields import CITextField, JSONField, ArrayField

from core.models import Repository

log = logging.getLogger(__name__)


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
    plan = models.CharField(max_length=10, null=True)
    # plan_provider
    plan_user_count = models.SmallIntegerField(null=True)
    plan_auto_activate = models.BooleanField(null=True)
    plan_activated_users = ArrayField(models.IntegerField(null=True))
    did_trial = models.BooleanField(null=True)
    free = models.SmallIntegerField()
    invoice_details = models.TextField(null=True)
    delinquent = models.BooleanField(null=True)
    yaml = JSONField(null=True)
    updatestamp = models.DateTimeField(auto_now=True)
    organizations = ArrayField(models.IntegerField(null=True), null=True)
    admins = ArrayField(models.IntegerField(null=True), null=True)
    integration_id = models.IntegerField(null=True)
    permission = ArrayField(models.IntegerField(null=True), null=True)
    bot = models.IntegerField(null=True)

    @property
    def has_legacy_plan(self):
        return not self.plan.startswith('users')

    @property
    def repo_credits(self):
        # Returns the number of private repo credits remaining
        # Only meaningful for legacy plans
        V4_PLAN_PREFIX = 'v4-'

        if not self.has_legacy_plan:
            return float('inf')
        if self.plan.startswith(V4_PLAN_PREFIX):
            repos = self.plan[3:-1]
        else:
            repos = self.plan[:-1]
        return int(repos) - self.repository_set.filter(active=True, private=True).count()

    @property
    def orgs(self):
        return Owner.objects.filter(ownerid__in=self.organizations)

    @property
    def is_active(self):
        return True

    @property
    def active_repos(self):
        active_repos = Repository.objects.filter(
            active=True, author=self.ownerid).order_by('-updatestamp')

        if len(active_repos):
            return active_repos

    @property
    def is_anonymous(self):
        return False

    @property
    def is_authenticated(self):
        return True

    def has_perms(self, *args, **kwargs):
        # TODO : Implement real permissioning system
        return True


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
