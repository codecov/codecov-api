from traceback import format_stack

import requests
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from codecov_auth.constants import GITLAB_BASE_URL

GITLAB_PAYLOAD_AVATAR_URL_KEY = "avatar_url"


def get_gitlab_url(email, size):
    res = requests.get(
        "{}/api/v4/avatar?email={}&size={}".format(GITLAB_BASE_URL, email, size)
    )
    url = ""
    if res.status_code == 200:
        data = res.json()
        try:
            url = data[GITLAB_PAYLOAD_AVATAR_URL_KEY]
        except KeyError:
            pass

    return url


def current_user_part_of_org(owner, org):
    if owner is None:
        return False
    if owner == org:
        return True
    # owner is a direct member of the org
    orgs_of_user = owner.organizations or []
    return org.ownerid in orgs_of_user


# https://stackoverflow.com/questions/7905106/adding-a-log-entry-for-an-action-by-a-user-in-a-django-ap


class History:
    @staticmethod
    def log(objects, message, user, action_flag=None, add_traceback=False):
        """
        Log an action in the admin log
        :param objects: Objects being operated on
        :param message: Message to log
        :param user: User performing action
        :param action_flag: Type of action being performed
        :param add_traceback: Add the stack trace to the message
        """
        if action_flag is None:
            action_flag = CHANGE

        if type(objects) is not list:
            objects = [objects]

        if add_traceback:
            message = f"{message}: {format_stack()}"

        for obj in objects:
            if not obj:
                continue

            LogEntry.objects.log_action(
                user_id=user.pk,
                content_type_id=ContentType.objects.get_for_model(obj).pk,
                object_repr=str(obj),
                object_id=obj.ownerid,
                change_message=message,
                action_flag=action_flag,
            )
