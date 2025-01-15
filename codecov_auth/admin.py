import logging
from datetime import timedelta
from typing import Optional, Sequence

import django.forms as forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.models import LogEntry
from django.db.models import OuterRef, Subquery
from django.db.models.fields import BLANK_CHOICE_DASH
from django.forms import CheckboxInput, Select, Textarea
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.html import format_html
from shared.django_apps.codecov_auth.models import (
    Account,
    AccountsUsers,
    InvoiceBilling,
    Plan,
    StripeBilling,
    Tier,
)
from shared.plan.service import PlanService

from codecov.admin import AdminMixin
from codecov.commands.exceptions import ValidationError
from codecov_auth.helpers import History
from codecov_auth.models import OrganizationLevelToken, Owner, SentryUser, Session, User
from codecov_auth.services.org_level_token_service import OrgLevelTokenService
from services.task import TaskService
from utils.services import get_short_service_name

log = logging.getLogger(__name__)


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
    can_delete = False
    can_edit = False


class OwnerUserInline(admin.TabularInline):
    model = Owner
    max_num = 5
    extra = 0
    verbose_name_plural = "Owners (read only)"
    verbose_name = "Owner"
    exclude = ("oauth_token",)
    can_delete = False

    readonly_fields = [
        "name",
        "username",
        "email",
        "service",
        "student",
    ]

    fields = [] + readonly_fields


@admin.register(User)
class UserAdmin(AdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "email",
    )
    inlines = [AccountsUsersInline, OwnerUserInline]
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
    extra = 0
    can_delete = False
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

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        field = form.base_fields["account"]
        field.widget.can_add_related = False
        field.widget.can_change_related = False
        field.widget.can_delete_related = False
        return form


class StripeBillingInline(admin.StackedInline):
    can_delete = False
    extra = 0
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

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        field = form.base_fields["account"]
        field.widget.can_add_related = False
        field.widget.can_change_related = False
        field.widget.can_delete_related = False
        return form


class OwnerOrgInline(admin.TabularInline):
    model = Owner
    max_num = 100
    extra = 0
    verbose_name_plural = "Organizations (read only)"
    verbose_name = "Organization"
    exclude = ("oauth_token",)
    can_delete = False

    readonly_fields = [
        "name",
        "username",
        "plan",
        "plan_activated_users",
        "service",
    ]

    fields = [] + readonly_fields


def find_and_remove_stale_users(
    orgs: Sequence[Owner], date_threshold: timedelta | None = None
) -> tuple[set[int], set[int]]:
    """
    This functions finds all the stale `plan_activated_users` in any of the given `orgs`.

    It then removes all those stale users from the given `orgs`,
    returning the set of stale users (`ownerid`), and the set of `orgs` that were updated (`ownerid`).

    A user is considered stale if it had no API or login `Session` or any opened PR within `date_threshold`.
    If no `date_threshold` is given, it defaults to *90 days*.
    """

    active_users = set()
    for org in orgs:
        active_users.update(set(org.plan_activated_users))

    if not active_users:
        return (set(), set())

    # NOTE: the `annotate_last_pull_timestamp` manager/queryset method does the same `annotate` with `Subquery`.
    sessions = Session.objects.filter(owner=OuterRef("pk")).order_by("-lastseen")
    resolved_users = list(
        Owner.objects.filter(ownerid__in=active_users)
        .annotate(latest_session=Subquery(sessions.values("lastseen")[:1]))
        .annotate_last_pull_timestamp()
        .values_list("ownerid", "latest_session", "last_pull_timestamp", named=True)
    )

    threshold = timezone.now() - (date_threshold or timedelta(days=90))

    def is_stale(user: dict) -> bool:
        return (user.latest_session is None or user.latest_session < threshold) and (
            # NOTE: `last_pull_timestamp` is not timezone-aware, so we explicitly compare without timezones here
            user.last_pull_timestamp is None
            or user.last_pull_timestamp.replace(tzinfo=None)
            < threshold.replace(tzinfo=None)
        )

    stale_users = {user.ownerid for user in resolved_users if is_stale(user)}
    affected_orgs = {
        org for org in orgs if stale_users.intersection(set(org.plan_activated_users))
    }

    if not affected_orgs:
        return (set(), set())

    # TODO: it might make sense to run all this within a transaction and locking the `affected_orgs` for update,
    # as we have a slight chance of races between querying the `orgs` at the very beginning and updating them here:
    for org in affected_orgs:
        org.plan_activated_users = list(
            set(org.plan_activated_users).difference(stale_users)
        )
    Owner.objects.bulk_update(affected_orgs, ["plan_activated_users"])

    return (stale_users, {org.ownerid for org in affected_orgs})


@admin.register(Account)
class AccountAdmin(AdminMixin, admin.ModelAdmin):
    list_display = ("name", "is_active", "organizations_count", "all_user_count")
    search_fields = ("name__iregex", "id")
    search_help_text = "Search by name (can use regex), or id (exact)"
    inlines = [OwnerOrgInline, StripeBillingInline, InvoiceBillingInline]
    actions = ["seat_check", "link_users_to_account", "deactivate_stale_users"]

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

    @admin.action(description="Deactivate all stale `plan_activated_users`")
    def deactivate_stale_users(self, request, queryset):
        orgs = [org for account in queryset for org in account.organizations.all()]
        stale_users, updated_orgs = find_and_remove_stale_users(orgs)

        if not stale_users or not updated_orgs:
            self.message_user(
                request,
                "No stale users found in selected accounts / organizations.",
                messages.INFO,
            )
        else:
            self.message_user(
                request,
                f"Removed {len(stale_users)} stale users from {len(updated_orgs)} affected organizations.",
                messages.SUCCESS,
            )

    @admin.action(
        description="Count current plan_activated_users across all Organizations"
    )
    def seat_check(self, request, queryset):
        self.link_users_to_account(request, queryset, dry_run=True)

    @admin.action(description="Link Users to Account")
    def link_users_to_account(self, request, queryset, dry_run=False):
        for account in queryset:
            account_plan_activated_user_ownerids = set()
            for org in account.organizations.all():
                account_plan_activated_user_ownerids.update(
                    set(org.plan_activated_users)
                )

            account_plan_activated_user_owners = Owner.objects.filter(
                ownerid__in=account_plan_activated_user_ownerids
            ).prefetch_related("user")

            non_student_count = account_plan_activated_user_owners.exclude(
                student=True
            ).count()
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

            owners_without_user_objects = account_plan_activated_user_owners.filter(
                user__isnull=True
            )
            owners_with_new_user_objects = []
            for userless_owner in owners_without_user_objects:
                new_user = User.objects.create(
                    name=userless_owner.name, email=userless_owner.email
                )
                userless_owner.user = new_user
                owners_with_new_user_objects.append(userless_owner)
            total = Owner.objects.bulk_update(owners_with_new_user_objects, ["user"])
            self.message_user(
                request,
                f"Created a User for {total} Owners",
                messages.INFO,
            )
            if total > 0:
                log.info(
                    f"Admin operation for {account} - Created a User for {total} Owners",
                    extra=dict(
                        owners_with_new_user_objects=[
                            str(owner) for owner in owners_with_new_user_objects
                        ],
                        account_id=account.id,
                    ),
                )

            # redo this query to get all Owners and Users
            account_plan_activated_user_owners = Owner.objects.filter(
                ownerid__in=account_plan_activated_user_ownerids
            ).prefetch_related("user")

            already_linked_account_users = AccountsUsers.objects.filter(account=account)

            not_yet_linked_owners = account_plan_activated_user_owners.exclude(
                user_id__in=already_linked_account_users.values_list(
                    "user_id", flat=True
                )
            )

            account_users_that_should_be_unlinked = (
                already_linked_account_users.exclude(
                    user_id__in=account_plan_activated_user_owners.values_list(
                        "user_id", flat=True
                    )
                )
            )
            deleted_ids_for_log = list(
                account_users_that_should_be_unlinked.values_list("id", flat=True)
            )
            deleted_count, _ = account_users_that_should_be_unlinked.delete()

            new_accounts_users = []
            for owner in not_yet_linked_owners:
                new_account_user = AccountsUsers(
                    user_id=owner.user_id, account_id=account.id
                )
                new_accounts_users.append(new_account_user)
            total = AccountsUsers.objects.bulk_create(new_accounts_users)
            self.message_user(
                request,
                f"Created {len(total)} AccountsUsers, removed {deleted_count} AccountsUsers",
                messages.SUCCESS,
            )
            if len(total) > 0 or deleted_count > 0:
                log.info(
                    f"Admin operation for {account} - Created {len(total)} AccountsUsers, removed {deleted_count} AccountsUsers",
                    extra=dict(
                        new_accounts_users=total,
                        removed_accounts_users_ids=deleted_ids_for_log,
                        account_id=account.id,
                    ),
                )


@admin.register(Owner)
class OwnerAdmin(AdminMixin, admin.ModelAdmin):
    exclude = ("oauth_token",)
    list_display = ("name", "username", "email", "service")
    readonly_fields = []
    search_fields = ("name__iregex", "username__iregex", "email__iregex", "ownerid")
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
        "delinquent",
        "integration_id",
        "bot",
        "stripe_customer_id",
        "stripe_subscription_id",
        "organizations",
        "max_upload_limit",
        "account",
        "upload_token_required_for_public_repos",
    )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)
        PLANS_CHOICES = [
            (x, x)
            for x in Plan.objects.filter(is_active=True).values_list("name", flat=True)
        ]
        form.base_fields["plan"].widget = Select(
            choices=BLANK_CHOICE_DASH + PLANS_CHOICES
        )
        form.base_fields["uses_invoice"].widget = CheckboxInput()

        is_superuser = request.user.is_superuser
        if not is_superuser:
            form.base_fields["staff"].disabled = True

        field = form.base_fields["account"]
        field.widget.can_add_related = False
        field.widget.can_change_related = False
        field.widget.can_delete_related = False

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


@admin.register(AccountsUsers)
class AccountsUsersAdmin(AdminMixin, admin.ModelAdmin):
    list_display = ("id", "user", "account")
    search_fields = (
        "account__name",
        "account__id__iexact",
        "id__iexact",
        "user__id__iexact",
        "user__name",
        "user__email",
    )
    search_help_text = "Search by account name, account id (exact), id (exact), user id (exact), user's name or email"
    autocomplete_fields = ("account", "user")

    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
    ]

    fields = readonly_fields + ["account", "user"]


class PlansInline(admin.TabularInline):
    model = Plan
    extra = 1
    verbose_name_plural = "Plans (click save to commit changes)"
    verbose_name = "Plan"
    fields = [
        "name",
        "marketing_name",
        "base_unit_price",
        "billing_rate",
        "max_seats",
        "monthly_uploads_limit",
        "paid_plan",
        "is_active",
        "stripe_id",
    ]
    formfield_overrides = {
        Plan._meta.get_field("benefits"): {"widget": Textarea(attrs={"rows": 3})},
    }


@admin.register(Tier)
class TierAdmin(admin.ModelAdmin):
    list_display = (
        "tier_name",
        "bundle_analysis",
        "test_analytics",
        "flaky_test_detection",
        "project_coverage",
        "private_repo_support",
    )
    list_editable = (
        "bundle_analysis",
        "test_analytics",
        "flaky_test_detection",
        "project_coverage",
        "private_repo_support",
    )
    search_fields = ("tier_name__iregex",)
    inlines = [PlansInline]
    fields = [
        "tier_name",
        "bundle_analysis",
        "test_analytics",
        "flaky_test_detection",
        "project_coverage",
        "private_repo_support",
    ]


class PlanAdminForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = "__all__"

    def clean_base_unit_price(self) -> int | None:
        base_unit_price = self.cleaned_data.get("base_unit_price")
        if base_unit_price is not None and base_unit_price < 0:
            raise forms.ValidationError("Base unit price cannot be negative.")
        return base_unit_price

    def clean_max_seats(self) -> int | None:
        max_seats = self.cleaned_data.get("max_seats")
        if max_seats is not None and max_seats < 0:
            raise forms.ValidationError("Max seats cannot be negative.")
        return max_seats

    def clean_monthly_uploads_limit(self) -> int | None:
        monthly_uploads_limit = self.cleaned_data.get("monthly_uploads_limit")
        if monthly_uploads_limit is not None and monthly_uploads_limit < 0:
            raise forms.ValidationError("Monthly uploads limit cannot be negative.")
        return monthly_uploads_limit


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    form = PlanAdminForm
    list_display = (
        "name",
        "marketing_name",
        "is_active",
        "tier",
        "paid_plan",
        "billing_rate",
        "base_unit_price",
        "max_seats",
        "monthly_uploads_limit",
    )
    list_filter = ("is_active", "paid_plan", "billing_rate", "tier")
    search_fields = ("name__iregex", "marketing_name__iregex")
    fields = [
        "tier",
        "name",
        "marketing_name",
        "base_unit_price",
        "benefits",
        "billing_rate",
        "is_active",
        "max_seats",
        "monthly_uploads_limit",
        "paid_plan",
        "stripe_id",
    ]
    formfield_overrides = {
        Plan._meta.get_field("benefits"): {"widget": Textarea(attrs={"rows": 3})},
    }
    autocomplete_fields = ["tier"]  # a dropdown for selecting related Tiers
