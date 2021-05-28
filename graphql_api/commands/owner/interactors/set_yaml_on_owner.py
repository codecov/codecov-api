from asgiref.sync import sync_to_async
import html
import yaml

from codecov_auth.models import Owner
from graphql_api.actions.owner import current_user_part_of_org
from graphql_api.commands.base import BaseInteractor
from graphql_api.commands.exceptions import Unauthenticated


class SetYamlOnOwnerInteractor(BaseInteractor):
    def fetch_owner(self, username):
        service = self.current_user.service
        return Owner.objects.get(username=username, service=service)

    def validate(self):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    def authorization(self):
        if not current_user_part_of_org(self.current_user, self.owner):
            raise Unauthenticated()

    def convert_yaml_to_dict(self, yaml_input):
        yaml_safe = html.escape(yaml_input)
        yaml_as_dict = yaml.safe_load(yaml_safe)
        return yaml_as_dict

    @sync_to_async
    def execute(self, username, yaml_input):
        self.validate()
        self.owner = self.fetch_owner(username)
        self.authorization()
        self.owner.yaml = self.convert_yaml_to_dict(yaml_input)
        self.owner.save()
        return self.owner
