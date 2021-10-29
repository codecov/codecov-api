from django.contrib import admin
from django.core.paginator import Paginator
from django.db import connections
from django.utils.functional import cached_property

from codecov_auth.models import RepositoryToken
from core.models import Repository


class RepositoryTokenInline(admin.TabularInline):
    model = RepositoryToken
    readonly_fields = ["key"]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    class Meta:
        readonly_fields = ("key",)


class EstimatedCountPaginator(Paginator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.object_list.count = self.count

    @cached_property
    def count(self):
        # Inspired by https://code.djangoproject.com/ticket/8408
        if self.object_list.query.where:
            return self.object_list.count()

        db_table = self.object_list.model._meta.db_table
        cursor = connections[self.object_list.db].cursor()
        cursor.execute("SELECT reltuples FROM pg_class WHERE relname = %s", (db_table,))
        result = cursor.fetchone()
        if not result:
            return 0
        return int(result[0])


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    inlines = [RepositoryTokenInline]
    list_display = ("name", "service_id", "author")
    search_fields = ("author__username__exact",)
    show_full_result_count = False
    paginator = EstimatedCountPaginator
    fields = (
        "name",
        "author",
        "service_id",
        "private",
        "updatestamp",
        "active",
        "language",
        "fork",
        "branch",
        "upload_token",
        "yaml",
        "cache",
        "image_token",
        "using_integration",
        "hookid",
        "bot",
        "activated",
        "deleted",
    )

    def get_readonly_fields(self, request, obj=None):
        return self.fields

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, _, obj=None):
        return False
