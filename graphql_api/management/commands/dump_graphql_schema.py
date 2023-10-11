from graphql_api.schema import schema
from graphql import print_schema

from django.core.management.base import BaseCommand, CommandParser

class Command(BaseCommand):
    help = "Dump the full GraphQL schema to a file"

    def add_arguments(self, parser: CommandParser) -> None:
        pass

    def handle(self, *args, **options) -> None:
        content = print_schema(schema)
        with open("graphql_api/schema.graphql", "w") as f:
            f.write(content)