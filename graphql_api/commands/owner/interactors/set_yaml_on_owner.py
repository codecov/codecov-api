from asgiref.sync import sync_to_async
import html
import yaml

from codecov_auth.models import Owner
from graphql_api.actions.owner import current_user_part_of_org
from graphql_api.commands.base import BaseInteractor
from graphql_api.commands.exceptions import (
    Unauthenticated,
    ValidationError,
    Unauthorized,
)
from shared.validation.yaml import validate_yaml
from shared.validation.exceptions import InvalidYamlException


class SetYamlOnOwnerInteractor(BaseInteractor):
    def validate(self):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    def authorization(self):
        if not current_user_part_of_org(self.current_user, self.owner):
            raise Unauthorized()

    def convert_yaml_to_dict(self, yaml_input):
        yaml_safe = html.escape(yaml_input)
        yaml_dict = yaml.safe_load(yaml_safe)
        if not isinstance(yaml_dict, dict):
            raise ValidationError(f"Bad Yaml format")
        try:
            return validate_yaml(yaml_dict)
        except InvalidYamlException as e:
            message = f"Error at {str(e.error_location)}: {e.error_message}"
            raise ValidationError(message)

    @sync_to_async
    def execute(self, username, yaml_input):
        self.validate()
        self.owner = Owner.objects.get(username=username, service=self.service)
        self.authorization()
        self.owner.yaml = self.convert_yaml_to_dict(yaml_input)
        self.owner.save()
        return self.owner
