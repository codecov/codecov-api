from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django_better_admin_arrayfield.admin.mixins import DynamicArrayMixin
from django_better_admin_arrayfield.forms.fields import DynamicArrayField
from django_better_admin_arrayfield.forms.widgets import DynamicArrayTextareaWidget
from django_better_admin_arrayfield.models.fields import ArrayField

# from shared.django_apps.core.models import
from shared.django_apps.codecov_auth.models import Owner

# from shared.django_apps.codecov_auth.models import Owner
from shared.django_apps.core.models import Repository
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
                new_obj.changed_fields[
                    changed_field
                ] = f"prev value: {prev_value}, new value: {new_value}"

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
    list_display = ["name", "number_of_variants"]
    search_fields = ["name"]
    inlines = [FeatureFlagVariantInline]

    def number_of_variants(self, obj):
        return obj.variants.count()

    number_of_variants.short_description = "# of Variants"


class DDynamicArrayWidget(forms.TextInput):

    template_name = "./a.html"

    def __init__(self, *args, **kwargs):
        self.subwidget_form = kwargs.pop("subwidget_form", forms.TextInput)
        super().__init__(*args, **kwargs)

    def get_context(self, name, value, attrs):
        self.field_name = name
        context_value = value or [""]
        context = super().get_context(name, context_value, attrs)
        final_attrs = context["widget"]["attrs"]
        id_ = context["widget"]["attrs"].get("id")
        context["widget"]["is_none"] = value is None

        subwidgets = []
        for index, item in enumerate(context["widget"]["value"]):
            widget_attrs = final_attrs.copy()
            if id_:
                widget_attrs["id"] = "{id_}_{index}".format(id_=id_, index=index)
            widget = self.subwidget_form()
            widget.is_required = self.is_required
            subwidgets.append(widget.get_context(name, item, widget_attrs)["widget"])

        context["widget"]["subwidgets"] = subwidgets
        return context

    def value_from_datadict(self, data, files, name):
        print("DATADICT", data, files, name)
        try:
            getter = data.getlist
            return [value for value in getter(name) if value]
        except AttributeError:
            return data.get(name)

    def value_omitted_from_data(self, data, files, name):
        return False

    def format_value(self, value):
        print("THIS IS THE VALUE", value, self.field_name)
        result = []
        if self.field_name == "override_owner_ids":
            for id in value:
                try:
                    if id:
                        obj = Owner.objects.get(ownerid=id)
                        result.append(obj.__str__())
                except Owner.DoesNotExist:
                    pass
        elif self.field_name == "override_repo_ids":
            for id in value:
                try:
                    if id:
                        obj = Repository.objects.get(repoid=id)
                        result.append(obj.__str__())
                except Repository.DoesNotExist:
                    pass
        print(result)
        return result


class FeatureFlagVariantAdmin(admin.ModelAdmin, DynamicArrayMixin):
    list_display = ["variant_id", "name", "feature_flag"]
    search_fields = ["variant_id", "name", "feature_flag__name"]
    form = AutocompleteSearchForm
    formfield_overrides = {ArrayField: {"widget": DDynamicArrayWidget}}


admin.site.register(FeatureFlag, FeatureFlagAdmin)
admin.site.register(FeatureFlagVariant, FeatureFlagVariantAdmin)
