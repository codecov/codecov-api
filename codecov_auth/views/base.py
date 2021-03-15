from json import dumps
import logging

from django.utils import timezone
from django.conf import settings
from shared.analytics_tracking import track_event, track_user

from codecov_auth.helpers import create_signed_value
from codecov_auth.models import Session, Owner
from utils.encryption import encryptor
from utils.config import get_config
from services.task import TaskService
from services.redis_configuration import get_redis_connection
from services.segment import SegmentService

log = logging.getLogger(__name__)


class LoginMixin(object):
    segment_service = SegmentService()

    def get_is_enterprise(self):
        # TODO Change when rolling out enterprise
        return False

    def get_or_create_org(self, single_organization):
        owner, was_created = Owner.objects.get_or_create(
            service="github", service_id=single_organization["id"]
        )
        return owner

    def login_from_user_dict(self, user_dict, request, response):
        user_orgs = user_dict["orgs"]
        formatted_orgs = [
            dict(username=org["username"], id=str(org["id"])) for org in user_orgs
        ]
        upserted_orgs = []
        for org in formatted_orgs:
            upserted_orgs.append(self.get_or_create_org(org))
        if self.get_is_enterprise() and get_config(self.service, "organizations"):
            # TODO Change when rolling out enterprise
            pass
        self._check_user_count_limitations()
        user, is_new_user = self._get_or_create_user(user_dict)
        fields_to_update = []
        if user_dict.get("is_student") != user.student:
            user.student = user_dict.get("is_student")
            if user.student_created_at is None:
                user.student_created_at = timezone.now()
            user.student_updated_at = timezone.now()
            fields_to_update.extend(
                ["student", "student_created_at", "student_updated_at"]
            )
        if user.organizations is None:
            user.organizations = [o.ownerid for o in upserted_orgs]
            fields_to_update.extend(["organizations"])
        if user.bot is not None:
            log.info(
                "Clearing user bot field",
                extra=dict(ownerid=user.ownerid, old_bot=user.bot),
            )
            user.bot = None
            fields_to_update.append("bot")
        if fields_to_update:
            user.save(update_fields=fields_to_update)

        track_user(
            user.ownerid,
            {
                "username": user.username,
                "ownerid": user.ownerid,
                "student": user.student,
                "student_created_at": user.student_created_at,
            },
        )
        track_event(
            user.ownerid,
            "User Signed Up" if is_new_user else "User Signed In",
            {
                "organizations": formatted_orgs,
                "username": user.username,
                "userid_type": "user",
            },
        )
        self._set_proper_cookies_and_session(user, request, response)
        self._schedule_proper_tasks(user)
        log.info("User is logging in", extra=dict(ownerid=user.ownerid))
        return user

    def _set_proper_cookies_and_session(self, user, request, response):
        domain_to_use = settings.COOKIES_DOMAIN
        Session.objects.filter(
            owner_id=user.ownerid, type="login", ip=request.META.get("REMOTE_ADDR")
        ).delete()
        session = Session(
            owner=user,
            useragent=request.META.get("HTTP_USER_AGENT"),
            ip=request.META.get("REMOTE_ADDR"),
            lastseen=timezone.now(),
            type="login",
        )
        session.save()
        token = str(session.token)
        signed_cookie_value = create_signed_value(
            f"{self.cookie_prefix}-token", token, version=None
        )
        response.set_cookie(
            f"{self.cookie_prefix}-token", signed_cookie_value, domain=domain_to_use
        )
        response.set_cookie(
            f"{self.cookie_prefix}-username",
            user.username,
            domain=domain_to_use,
            httponly=True,
        )

    def _check_user_count_limitations(self):
        # TODO (Thiago): Do when on enterprise
        pass

    def _get_or_create_user(self, user_dict):
        fields_to_update = ["oauth_token", "private_access", "updatestamp"]
        login_data = user_dict["user"]
        owner, was_created = Owner.objects.get_or_create(
            service=f"{self.cookie_prefix}", service_id=login_data["id"]
        )
        if login_data["login"] != owner.username:
            fields_to_update.append("username")
            owner.username = login_data["login"]
        owner.oauth_token = encryptor.encode(login_data["access_token"]).decode()
        owner.private_access = user_dict["has_private_access"]
        if user_dict["user"].get("name"):
            owner.name = user_dict["user"]["name"]
            fields_to_update.append("name")
        if user_dict["user"].get("email"):
            owner.email = user_dict["user"].get("email")
            fields_to_update.append("email")
        owner.save(update_fields=fields_to_update)

        ## Segment tracking
        self.segment_service.identify_user(owner)
        self.segment_service.group(owner)
        if was_created:
            self.segment_service.user_signed_up(owner)
        else:
            self.segment_service.user_signed_in(owner)

        return (owner, was_created)

    def _schedule_proper_tasks(self, user):
        task_service = TaskService()
        redis = get_redis_connection()
        resp = task_service.refresh(user.ownerid, user.username)
        redis.hset("refresh", user.ownerid, dumps(resp.as_tuple()))
