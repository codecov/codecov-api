import html
from typing import Optional

import yaml
from shared.validation.exceptions import InvalidYamlException
from shared.yaml.validation import validate_yaml

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import (
    NotFound,
    Unauthenticated,
    Unauthorized,
    ValidationError,
)
from codecov.db import sync_to_async
from codecov_auth.constants import OWNER_YAML_TO_STRING_KEY
from codecov_auth.helpers import current_user_part_of_org
from codecov_auth.models import Owner


class SetYamlOnOwnerInteractor(BaseInteractor):
    def validate(self) -> None:
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    def authorize(self) -> None:
        if not current_user_part_of_org(self.current_owner, self.owner):
            raise Unauthorized()

    def get_owner(self, username: str) -> Owner:
        try:
            return Owner.objects.get(username=username, service=self.service)
        except Owner.DoesNotExist:
            raise NotFound()

    def convert_yaml_to_dict(self, yaml_input: str) -> Optional[dict]:
        yaml_safe = html.escape(yaml_input, quote=False)
        try:
            yaml_dict = yaml.safe_load(yaml_safe)
        except yaml.scanner.ScannerError as e:
            line = e.problem_mark.line
            column = e.problem_mark.column
            message = f"Syntax error at line {line+1}, column {column+1}: {e.problem}"
            raise ValidationError(message)
        if not yaml_dict:
            return None
        try:
            return validate_yaml(yaml_dict, show_secrets_for=None)
        except InvalidYamlException as e:
            message = f"Error at {str(e.error_location)}: {e.error_message}"
            raise ValidationError(message)

    @sync_to_async
    def execute(self, username: str, yaml_input: str) -> Owner:
        self.validate()
        self.owner = self.get_owner(username)
        self.authorize()
        self.owner.yaml = self.convert_yaml_to_dict(yaml_input)
        if self.owner.yaml:
            self.owner.yaml[OWNER_YAML_TO_STRING_KEY] = yaml_input
        self.owner.save()
        return self.owner
