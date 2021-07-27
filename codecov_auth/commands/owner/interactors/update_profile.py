from asgiref.sync import sync_to_async
from django import forms

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, ValidationError


class UpdateProfileForm(forms.Form):
    name = forms.CharField(required=False)
    email = forms.EmailField(required=False)


class UpdateProfileInteractor(BaseInteractor):
    def validate(self, **kwargs):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()
        form = UpdateProfileForm(kwargs)
        if not form.is_valid():
            # temporary solution to expose form errors until a better abstraction
            raise ValidationError(form.errors.as_json())

    def update_field(self, field_name, **kwargs):
        field = kwargs.get(field_name)
        if not field:
            return
        setattr(self.current_user, field_name, field)

    @sync_to_async
    def execute(self, **kwargs):
        self.validate(**kwargs)
        self.update_field("email", **kwargs)
        self.update_field("name", **kwargs)
        self.current_user.save()
        return self.current_user
