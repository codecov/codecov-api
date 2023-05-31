from django.contrib import admin

from codecov.admin import AdminMixin
from reports.models import ReportSession


@admin.register(ReportSession)
class ReportSessionAdmin(AdminMixin, admin.ModelAdmin):
    list_display = ("id", "external_id")
    show_full_result_count = False
    readonly_fields = ("external_id", "storage_path", "upload_type")
    search_fields = ("external_id",)
    fields = readonly_fields

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, _, obj=None):
        return False

    def has_change_permission(self, _, obj=None):
        return False
