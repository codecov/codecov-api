from django.conf import settings
from django.contrib import admin, messages
from django.shortcuts import redirect

from codecov_auth.models import Owner
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
        return fields

    def has_add_permission(self, _, obj=None):
        return False

    def has_delete_permission(self, _, obj=None):
        return False
