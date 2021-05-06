from asgiref.sync import sync_to_async

from services.task import TaskService


def is_syncing(current_user):
    return TaskService().is_refreshing(current_user.ownerid)


@sync_to_async
def trigger_sync(current_user):
    if not current_user.is_authenticated:
        return {"error": "unauthenticated"}
    TaskService().refresh(
        current_user.ownerid,
        current_user.username,
        using_integration=bool(current_user.integration_id),
    )
    return {}
