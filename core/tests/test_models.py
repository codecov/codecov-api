from django.forms import ValidationError
from django.test import TestCase

from .factories import RepositoryFactory


class RepoTests(TestCase):
    def test_clean_repo(self):
        repo = RepositoryFactory(using_integration=None)
        with self.assertRaises(ValidationError):
            repo.clean()
