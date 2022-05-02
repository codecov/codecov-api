from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from legacy_migrations.models import YamlHistory
from legacy_migrations.tests.factories import YamlHistoryFactory


class TestYamlHistory(TransactionTestCase):
    def test_get_pieces_of_model(self):
        owner = OwnerFactory()
        author = OwnerFactory()
        yaml = YamlHistoryFactory(author=author, ownerid=owner, message="some_message")

        assert yaml.ownerid == owner
        assert yaml.author == author
        assert yaml.message == "some_message"

        assert YamlHistory.objects.count() == 1
