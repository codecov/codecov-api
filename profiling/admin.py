from django.contrib import admin

from profiling.models import ProfilingCommit
from services.task import TaskService


def schedule_profiling_collection(modeladmin, request, queryset):
    task_service = TaskService()
    for profiling_commit in queryset:
        task_service.collect_profiling_commit(profiling_commit.id)


@admin.register(ProfilingCommit)
class ProfilingCommitAdmin(admin.ModelAdmin):
    actions = [schedule_profiling_collection]
    list_display = ("external_id", "version_identifier", "repository_id")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, _, obj=None):
        return False
