from django.contrib import admin
from django import forms
from core.models import Repository
from codecov_auth.models import RepositoryToken


class RepositoryTokenInline(admin.TabularInline):
    model = RepositoryToken
    readonly_fields = ["key"]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    class Meta:
        readonly_fields = ("key", )


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    inlines = [RepositoryTokenInline]
    list_display = ("name", "service_id", "author_id")
    search_fields = ("name__iexact",)
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
