from typing import Optional

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.models import LogEntry
from django.db.models.fields import BLANK_CHOICE_DASH
from django.forms import Select
from django.http import HttpRequest
from django.shortcuts import redirect
from django.utils.html import format_html

from codecov.admin import AdminMixin
from codecov_auth.helpers import History
from codecov_auth.models import OrganizationLevelToken, Owner, OwnerProfile
from codecov_auth.services.org_level_token_service import OrgLevelTokenService
from plan.constants import USER_PLAN_REPRESENTATIONS
from services.task import TaskService
from utils.services import get_short_service_name


def impersonate_owner(self, request, queryset):
    if queryset.count() != 1:
        self.message_user(
            request, "You must impersonate exactly one Owner.", level=messages.ERROR
        )
        return

    owner = queryset.first()
    response = redirect(
        f"{settings.CODECOV_URL}/{get_short_service_name(owner.service)}/"
    )

    # this cookie is read by the `ImpersonationMiddleware` and
    # will reset `request.current_owner` to the impersonated owner
    response.set_cookie(
        "staff_user",
        owner.ownerid,
        domain=settings.COOKIES_DOMAIN,
        samesite=settings.COOKIE_SAME_SITE,
    )
    History.log(
        Owner.objects.get(ownerid=owner.ownerid),
        "Impersonation successful",
        request.user,
    )
    return response


impersonate_owner.short_description = "Impersonate the selected owner"


class OwnerProfileInline(admin.TabularInline):
    model = OwnerProfile
    fk_name = "owner"
    fields = ["terms_agreement", "terms_agreement_at"]

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False


class OrgUploadTokenInline(admin.TabularInline):
    model = OrganizationLevelToken
    readonly_fields = ["token", "refresh"]
    fields = ["token", "valid_until", "token_type", "refresh"]
    extra = 0
    max_num = 1
    verbose_name = "Organization Level Token"

    def refresh(self, obj: OrganizationLevelToken):
        # 0 in this case refers to the 0th index of the inline
        # But there can only ever be 1 token per org, so it's fine to use that.
        return format_html(
            f'<input type="checkbox" name="organization_tokens-0-REFRESH" id="id_organization_tokens-0-REFRESH">'
        )

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_staff

    def has_add_permission(self, request: HttpRequest, obj: Optional[Owner]) -> bool:
        has_token = OrganizationLevelToken.objects.filter(owner=obj).count() > 0
        return (not has_token) and request.user.is_staff


@admin.register(Owner)
class OwnerAdmin(AdminMixin, admin.ModelAdmin):
    exclude = ("oauth_token",)
    list_display = ("name", "username", "email", "service")
    readonly_fields = []
    search_fields = ("username__iexact",)
    actions = [impersonate_owner]
    autocomplete_fields = ("bot",)
    inlines = [OrgUploadTokenInline, OwnerProfileInline]

    readonly_fields = (
        "ownerid",
        "username",
        "service",
        "email",
        "business_email",
        "name",
        "service_id",
        "createstamp",
        "parent_service_id",
        "root_parent_service_id",
        "private_access",
        "cache",
        "free",
        "invoice_details",
        "delinquent",
        "yaml",
        "updatestamp",
        "permission",
        "student",
        "student_created_at",
        "student_updated_at",
    )

    fields = readonly_fields + (
        "admins",
        "plan_auto_activate",
        "onboarding_completed",
        "staff",
        "plan",
        "plan_provider",
        "plan_user_count",
        "plan_activated_users",
        "integration_id",
        "bot",
        "stripe_customer_id",
        "stripe_subscription_id",
        "organizations",
        "max_upload_limit",
    )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)
        PLANS_CHOICES = [(x, x) for x in USER_PLAN_REPRESENTATIONS.keys()]
        form.base_fields["plan"].widget = Select(
            choices=BLANK_CHOICE_DASH + PLANS_CHOICES
        )

        is_superuser = request.user.is_superuser

        if not is_superuser:
            form.base_fields["staff"].disabled = True

        return form

    def has_add_permission(self, _, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def delete_queryset(self, request, queryset) -> None:
        for owner in queryset:
            TaskService().delete_owner(ownerid=owner.ownerid)

    def delete_model(self, request, obj) -> None:
        TaskService().delete_owner(ownerid=obj.ownerid)

    def get_deleted_objects(self, objs, request):
        (
            deleted_objects,
            model_count,
            perms_needed,
            protected,
        ) = super().get_deleted_objects(objs, request)

        if request.user and request.user.is_superuser:
            perms_needed = set()

        deleted_objects = ()
        return deleted_objects, model_count, perms_needed, protected

    def save_related(self, request: HttpRequest, form, formsets, change: bool) -> None:
        if formsets:
            token_formset = formsets[0]
            token_id = token_formset.data.get("organization_tokens-0-id")
            token_refresh = token_formset.data.get("organization_tokens-0-REFRESH")
            # token_id only exists if the token already exists (edit operation)
            if token_formset.is_valid() and token_id and token_refresh:
                OrgLevelTokenService.refresh_token(token_id)
        return super().save_related(request, form, formsets, change)


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    readonly_fields = (
        "action_time",
        "user",
        "content_type",
        "object_id",
        "object_repr",
        "action_flag",
        "change_message",
    )
    list_display = ["__str__", "action_time", "user", "change_message"]
    search_fields = ("object_repr", "change_message")

    # keep only view permission
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
