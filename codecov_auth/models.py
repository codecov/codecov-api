import uuid
import logging

from django.db import models
from django.contrib.postgres.fields import CITextField, JSONField, ArrayField

from internal_api.repo.models import Repository

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
    # plan
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
    def orgs(self):
        orgs = []

        if self.organizations is not None:
            if len(self.organizations):
                for ownerid in self.organizations:
                    org = Owner.objects.get(ownerid=ownerid)
                    orgs.append(org)
        
        return orgs

    @property
    def active_repos(self):
        active_repos = Repository.objects.filter(active=True, author=self.ownerid).order_by('-updatestamp')

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
    owner = models.ForeignKey(Owner, db_column='ownerid', on_delete=models.CASCADE)
    lastseen = models.DateTimeField()
    # type
