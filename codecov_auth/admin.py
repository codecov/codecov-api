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

    def get_readonly_fields(self, _, obj=None):
        fields = (
            list(self.readonly_fields)
            + [field.name for field in obj._meta.fields]
            + [field.name for field in obj._meta.many_to_many]
        )
        fields.remove("oauth_token")
        fields.remove("staff")
        return fields

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
