from django.contrib import admin

from .models import CommitComparison


@admin.register(CommitComparison)
class CommitComparisonAdmin(admin.ModelAdmin):
    list_display = (
        "get_base_commit",
        "get_compare_commit",
        "get_repo_name",
        "state",
        "created_at",
        "updated_at",
    )

    def get_base_commit(self, obj):
        return obj.base_commit.commitid

    get_base_commit.short_description = "Base Commit Sha"

    def get_compare_commit(self, obj):
        return obj.compare_commit.commitid

    get_compare_commit.short_description = "Compare Commit Sha"

    def get_repo_name(self, obj):
        return obj.base_commit.repository.name

    get_repo_name.short_description = "Repository name"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "base_commit", "compare_commit", "base_commit__repository"
        ).defer("base_commit__report", "compare_commit__report")

    def has_add_permission(self, *args, **kwargs):
        return False

    def has_delete_permission(self, *args, **kwargs):
        return True
