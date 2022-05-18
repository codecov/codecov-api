from django.conf import settings
from django.contrib import admin, messages
from django.shortcuts import redirect

from codecov_auth.models import Owner
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
    response.set_cookie(
        "staff_user",
        owner.username,
        domain=settings.COOKIES_DOMAIN,
        samesite=settings.COOKIE_SAME_SITE,
    )
    return response


impersonate_owner.short_description = "Impersonate the selected user"


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    exclude = ("oauth_token",)
    list_display = ("name", "username", "email", "service")
    readonly_fields = []
    search_fields = ("username__iexact",)
    actions = [impersonate_owner]
    autocomplete_fields = ("bot",)

    # the displayed fields
    fields = (
        "staff",
        "ownerid",
        "username",
        "service",
        "email",
        "business_email",
        "name",
        "service_id",
        "createstamp",
        "plan",
        "plan_provider",
        "plan_user_count",
        "plan_activated_users",
        "plan_auto_activate",
        "integration_id",
        "bot",
        "stripe_customer_id",
        "stripe_subscription_id",
        "parent_service_id",
        "root_parent_service_id",
        "private_access",
        "cache",
        "did_trial",
        "free",
        "invoice_details",
        "delinquent",
        "yaml",
        "updatestamp",
        "organizations",
        "admins",
        "permission",
        "student",
        "student_created_at",
        "student_updated_at",
        "onboarding_completed",
    )
    readonly_fields = (
        "ownerid",
        "username",
        "service",
        "email",
        "business_email",
        "name",
        "service_id",
        "createstamp",
        "plan_auto_activate",
        "parent_service_id",
        "root_parent_service_id",
        "private_access",
        "cache",
        "did_trial",
        "free",
        "invoice_details",
        "delinquent",
        "yaml",
        "updatestamp",
        "organizations",
        "admins",
        "permission",
        "student",
        "student_created_at",
        "student_updated_at",
        "onboarding_completed",
    )

    def save_model(self, request, new_owner, form, change) -> None:
        if change:
            old_owner = Owner.objects.get(ownerid=new_owner.ownerid)
            new_owner.changed_fields = dict()

            for changed_field in form.changed_data:
                prev_value = getattr(old_owner, changed_field)
                new_value = getattr(new_owner, changed_field)
                new_owner.changed_fields[
                    changed_field
                ] = f"prev value: {prev_value}, new value: {new_value}"

        return super().save_model(request, new_owner, form, change)

    def log_change(self, request, object, message):
        message.append(object.changed_fields)
        return super().log_change(request, object, message)

    def has_add_permission(self, _, obj=None):
        return False

    def has_delete_permission(self, _, obj=None):
        return False

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
        deleted_objects = ()
        return deleted_objects, model_count, perms_needed, protected
