from asgiref.sync import sync_to_async

from services.task import TaskService


def is_syncing(current_user):
    return TaskService().is_refreshing(current_user.ownerid)
