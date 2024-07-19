from typing import Optional

import django.forms as forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.models import LogEntry
from django.db.models.fields import BLANK_CHOICE_DASH
from django.forms import CheckboxInput, Select
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.utils.html import format_html
from shared.django_apps.codecov_auth.models import (
    Account,
    AccountsUsers,
    InvoiceBilling,
    StripeBilling,
)

from codecov.admin import AdminMixin
from codecov.commands.exceptions import ValidationError
from codecov_auth.helpers import History
from codecov_auth.models import OrganizationLevelToken, Owner, SentryUser, User
from codecov_auth.services.org_level_token_service import OrgLevelTokenService
from plan.constants import USER_PLAN_REPRESENTATIONS
from plan.service import PlanService
from services.task import TaskService
from utils.services import get_short_service_name


class ExtendTrialForm(forms.Form):
    end_date = forms.DateTimeField(
        label="Trial End Date (YYYY-MM-DD HH:MM:SS):", required=True
    )


def extend_trial(self, request, queryset):
    if "extend_trial" in request.POST:
        form = ExtendTrialForm(request.POST)
        if form.is_valid():
            for org in queryset:
                plan_service = PlanService(current_org=org)
                try:
                    plan_service.start_trial_manually(
                        current_owner=request.current_owner,
                        end_date=form.cleaned_data["end_date"],
                    )
                except ValidationError as e:
                    self.message_user(
                        request,
                        e.message + f" for {org.username}",
                        level=messages.ERROR,
                    )
                else:
                    self.message_user(
                        request, f"Successfully started trial for {org.username}"
                    )
            return
    else:
        form = ExtendTrialForm()

    return render(
        request,
        "admin/extend_trial_form.html",
        context={
            "form": form,
            "datasets": queryset,
        },
    )


extend_trial.short_description = "Start and extend trial up to a selected date"


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


class AccountsUsersInline(admin.TabularInline):
    model = AccountsUsers
    max_num = 10
    extra = 1
    verbose_name_plural = "Accounts Users (click save to commit changes)"
    verbose_name = "Account User"


@admin.register(User)
class UserAdmin(AdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "email",
    )
    readonly_fields = []
    inlines = [AccountsUsersInline]
    search_fields = (
        "name__iregex",
        "email__iregex",
    )

    readonly_fields = (
        "id",
        "external_id",
    )

    fields = readonly_fields + (
        "name",
        "email",
        "is_staff",
        "terms_agreement",
        "terms_agreement_at",
    )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)

        if not request.user.is_superuser:
            form.base_fields["is_staff"].disabled = True

        return form

    def has_add_permission(self, _, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SentryUser)
class SentryUserAdmin(AdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "email",
    )
    search_fields = (
        "name__iregex",
        "email__iregex",
    )
    readonly_fields = (
        "id",
        "external_id",
        "sentry_id",
        "user",
    )
    fields = readonly_fields + (
        "name",
        "email",
    )

    def has_add_permission(self, _, obj=None):
        return False

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
            '<input type="checkbox" name="organization_tokens-0-REFRESH" id="id_organization_tokens-0-REFRESH">'
        )

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_staff

    def has_add_permission(self, request: HttpRequest, obj: Optional[Owner]) -> bool:
        has_token = OrganizationLevelToken.objects.filter(owner=obj).count() > 0
        return (not has_token) and request.user.is_staff


class InvoiceBillingInline(admin.StackedInline):
    model = InvoiceBilling
    verbose_name_plural = "Invoice Billing"
    verbose_name = "Invoice Billing (click save to commit changes)"


@admin.register(InvoiceBilling)
class InvoiceBillingAdmin(AdminMixin, admin.ModelAdmin):
    list_display = ("id", "account", "is_active")
    search_fields = (
        "account__name",
        "account__id__iexact",
        "id__iexact",
        "account_manager",
    )
    search_help_text = (
        "Search by account name, account id (exact), id (exact), or account_manager"
    )
    autocomplete_fields = ("account",)

    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
    ]

    fields = readonly_fields + [
        "account",
        "account_manager",
        "invoice_notes",
        "is_active",
    ]


class StripeBillingInline(admin.StackedInline):
    model = StripeBilling
    verbose_name_plural = "Stripe Billing"
    verbose_name = "Stripe Billing (click save to commit changes)"


@admin.register(StripeBilling)
class StripeBillingAdmin(AdminMixin, admin.ModelAdmin):
    list_display = ("id", "account", "is_active")
    search_fields = (
        "account__name",
        "account__id__iexact",
        "id__iexact",
        "customer_id__iexact",
        "subscription_id__iexact",
    )
    search_help_text = "Search by account name, account id (exact), id (exact), customer_id (exact), or subscription_id (exact)"
    autocomplete_fields = ("account",)

    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
    ]

    fields = readonly_fields + [
        "account",
        "customer_id",
        "subscription_id",
        "is_active",
    ]


class OwnerOrgInline(admin.TabularInline):
    model = Owner
    max_num = 100
    extra = 0
    verbose_name_plural = "Organizations (read only)"
    verbose_name = "Organization"
    exclude = ("oauth_token",)

    readonly_fields = [
        "name",
        "username",
        "plan",
        "plan_activated_users",
        "service",
    ]

    fields = [] + readonly_fields


@admin.register(Account)
class AccountAdmin(AdminMixin, admin.ModelAdmin):
    list_display = ("name", "is_active", "organizations_count", "all_user_count")
    search_fields = ("name__iregex", "id")
    search_help_text = "Search by name (can use regex), or id (exact)"
    inlines = [OwnerOrgInline, StripeBillingInline, InvoiceBillingInline]
    actions = ["seat_check", "link_users_to_account"]

    readonly_fields = ["id", "created_at", "updated_at", "users"]

    fields = readonly_fields + [
        "name",
        "is_active",
        "plan",
        "plan_seat_count",
        "free_seat_count",
        "plan_auto_activate",
        "is_delinquent",
    ]

    @admin.action(
        description="Count current plan_activated_users across all Organizations"
    )
    def seat_check(self, request, queryset):
        self.link_users_to_account(request, queryset, dry_run=True)

    @admin.action(description="Link Users to Account")
    def link_users_to_account(self, request, queryset, dry_run=False):
        for account in queryset:
            all_plan_activated_user_ids = set()
            for org in account.organizations.all():
                all_plan_activated_user_ids.update(set(org.plan_activated_users))

            all_plan_activated_users = Owner.objects.filter(
                ownerid__in=all_plan_activated_user_ids
            ).prefetch_related("user")

            non_student_count = all_plan_activated_users.exclude(student=True).count()
            total_seats_for_account = account.plan_seat_count + account.free_seat_count
            if non_student_count > total_seats_for_account:
                self.message_user(
                    request,
                    f"Request failed: Account plan does not have enough seats; "
                    f"current plan activated users (non-students): {non_student_count}, total seats for account: {total_seats_for_account}",
                    messages.ERROR,
                )
                return
            if dry_run:
                self.message_user(
                    request,
                    f"Request succeeded: Account plan has enough seats! "
                    f"current plan activated users (non-students): {non_student_count}, total seats for account: {total_seats_for_account}",
                    messages.SUCCESS,
                )
                return

            owners_without_user_objects = all_plan_activated_users.filter(
                user__isnull=True
            )
            userless_owners = []
            for userless_owner in owners_without_user_objects:
                new_user = User.objects.create()
                userless_owner.user = new_user
                userless_owners.append(userless_owner)
            total = Owner.objects.bulk_update(userless_owners, ["user"])
            self.message_user(
                request,
                f"Created a User for {total} Owners",
                messages.INFO,
            )

            new_accounts_users = []
            # redo this query to get all Owners and Users
            all_plan_activated_users = Owner.objects.filter(
                ownerid__in=all_plan_activated_users
            ).prefetch_related("user")
            already_linked_users = AccountsUsers.objects.filter(
                account=account
            ).values_list("user_id", flat=True)
            not_yet_linked_owners = all_plan_activated_users.exclude(
                user_id__in=already_linked_users
            )
            for owner in not_yet_linked_owners:
                new_account_user = AccountsUsers(
                    user_id=owner.user_id, account_id=account.id
                )
                new_accounts_users.append(new_account_user)

            total = AccountsUsers.objects.bulk_create(new_accounts_users)
            self.message_user(
                request,
                f"Created {len(total)} AccountsUsers",
                messages.SUCCESS,
            )


@admin.register(Owner)
class OwnerAdmin(AdminMixin, admin.ModelAdmin):
    exclude = ("oauth_token",)
    list_display = ("name", "username", "email", "service")
    readonly_fields = []
    search_fields = ("name__iregex", "username__iregex", "email__iregex")
    actions = [impersonate_owner, extend_trial]
    autocomplete_fields = ("bot", "account")
    inlines = [OrgUploadTokenInline]

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
        "user",
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
        "uses_invoice",
        "integration_id",
        "bot",
        "stripe_customer_id",
        "stripe_subscription_id",
        "organizations",
        "max_upload_limit",
        "account",
    )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)
        PLANS_CHOICES = [(x, x) for x in USER_PLAN_REPRESENTATIONS.keys()]
        form.base_fields["plan"].widget = Select(
            choices=BLANK_CHOICE_DASH + PLANS_CHOICES
        )
        form.base_fields["uses_invoice"].widget = CheckboxInput()

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
