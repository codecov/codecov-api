from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django_better_admin_arrayfield.admin.mixins import DynamicArrayMixin
from shared.django_apps.rollouts.models import FeatureFlag, FeatureFlagVariant

from codecov.forms import AutocompleteSearchForm


class AdminMixin(object):
    def save_model(self, request, new_obj, form, change) -> None:
        if change:
            old_obj = self.model.objects.get(pk=new_obj.pk)
            new_obj.changed_fields = dict()

            for changed_field in form.changed_data:
                prev_value = getattr(old_obj, changed_field)
                new_value = getattr(new_obj, changed_field)
                new_obj.changed_fields[changed_field] = (
                    f"prev value: {prev_value}, new value: {new_value}"
                )

        return super().save_model(request, new_obj, form, change)

    def log_change(self, request, object, message):
        message.append(object.changed_fields)
        return super().log_change(request, object, message)


class FeatureFlagVariantInline(admin.StackedInline):
    model = FeatureFlagVariant
    exclude = ["override_repo_ids", "override_owner_ids"]
    fields = ["name", "proportion", "value", "view_link"]
    readonly_fields = [
        "view_link",
    ]
    extra = 0

    def view_link(self, obj):
        link = reverse(
            "admin:rollouts_featureflagvariant_change", args=[obj.variant_id]
        )
        return format_html('<a href="{}">View</a>', link)

    view_link.short_description = "More Details"


class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active", "number_of_variants", "proportion_percentage"]
    search_fields = ["name"]
    inlines = [FeatureFlagVariantInline]

    def number_of_variants(self, obj):
        return obj.variants.count()

    number_of_variants.short_description = "# of Variants"

    def proportion_percentage(self, obj):
        return str(round(obj.proportion * 100)) + "%"

    proportion_percentage.short_description = "Experiment Proportion"


class FeatureFlagVariantAdmin(admin.ModelAdmin, DynamicArrayMixin):
    list_display = ["variant_id", "name", "feature_flag"]
    search_fields = ["variant_id", "name", "feature_flag__name"]
    form = AutocompleteSearchForm


admin.site.register(FeatureFlag, FeatureFlagAdmin)
admin.site.register(FeatureFlagVariant, FeatureFlagVariantAdmin)
