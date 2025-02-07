from django import forms
from django.contrib import admin
from django.core.paginator import Paginator
from django.db import connections
from django.utils.functional import cached_property

from codecov.admin import AdminMixin
from codecov_auth.models import RepositoryToken
from core.models import Pull, Repository
from services.task.task import TaskService


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


class RepositoryAdminForm(forms.ModelForm):
    # the model field has null=True but not blank=True, so we have to add a workaround
    # to be able to clear out this field through the django admin
    webhook_secret = forms.CharField(required=False, empty_value=None)
    yaml = forms.JSONField(required=False)
    using_integration = forms.BooleanField(required=False)
    hookid = forms.CharField(required=False, empty_value=None)

    class Meta:
        model = Repository
        fields = "__all__"


@admin.register(Repository)
class RepositoryAdmin(AdminMixin, admin.ModelAdmin):
    inlines = [RepositoryTokenInline]
    list_display = ("name", "service_id", "author")
    search_fields = ("author__username__exact",)
    show_full_result_count = False
    autocomplete_fields = ("bot",)
    form = RepositoryAdminForm

    paginator = EstimatedCountPaginator

    readonly_fields = (
        "name",
        "author",
        "service_id",
        "updatestamp",
        "active",
        "language",
        "fork",
        "upload_token",
        "yaml",
        "image_token",
        "hookid",
        "activated",
        "deleted",
    )
    fields = readonly_fields + (
        "bot",
        "using_integration",
        "branch",
        "private",
        "webhook_secret",
    )

    def has_add_permission(self, _, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def delete_queryset(self, request, queryset) -> None:
        for repo in queryset:
            TaskService().flush_repo(repository_id=repo.repoid)

    def delete_model(self, request, obj) -> None:
        TaskService().flush_repo(repository_id=obj.repoid)


@admin.register(Pull)
class PullsAdmin(AdminMixin, admin.ModelAdmin):
    list_display = ("pullid", "repository", "author")
    show_full_result_count = False
    paginator = EstimatedCountPaginator
    readonly_fields = (
        "repository",
        "id",
        "pullid",
        "issueid",
        "title",
        "base",
        "head",
        "user_provided_base_sha",
        "compared_to",
        "commentid",
        "author",
        "updatestamp",
        "diff",
        "flare",
    )
    fields = readonly_fields + ("state",)

    @admin.display(description="flare")
    def flare(self, instance):
        return instance.flare

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, _, obj=None):
        return False
