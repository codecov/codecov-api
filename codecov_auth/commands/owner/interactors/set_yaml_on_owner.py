from asgiref.sync import sync_to_async
import html
import yaml

from codecov_auth.models import Owner
from graphql_api.actions.owner import current_user_part_of_org
from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import (
    Unauthenticated,
    ValidationError,
    Unauthorized,
    NotFound,
)
from shared.validation.yaml import validate_yaml
from shared.validation.exceptions import InvalidYamlException


class SetYamlOnOwnerInteractor(BaseInteractor):
    def validate(self):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    def authorize(self):
        if not current_user_part_of_org(self.current_user, self.owner):
            raise Unauthorized()

    def get_owner(self, username):
        try:
            return Owner.objects.get(username=username, service=self.service)
        except Owner.DoesNotExist:
            raise NotFound()

    def convert_yaml_to_dict(self, yaml_input):
        yaml_safe = html.escape(yaml_input, quote=False)
        yaml_dict = yaml.safe_load(yaml_safe)
        if not yaml_dict:
            return None
        try:
            return validate_yaml(yaml_dict)
        except InvalidYamlException as e:
            message = f"Error at {str(e.error_location)}: {e.error_message}"
            raise ValidationError(message)

    @sync_to_async
    def execute(self, username, yaml_input):
        self.validate()
        self.owner = self.get_owner(username)
        self.authorize()
        self.owner.yaml = self.convert_yaml_to_dict(yaml_input)
        self.owner.save()
        return self.owner
