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
