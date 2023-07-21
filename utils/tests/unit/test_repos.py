from django.test import TestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from utils.repos import get_bot_user


class RepoUtilsTests(TestCase):
    def test_repo_bot_user_bot(self):
        bot = OwnerFactory()
        repo = RepositoryFactory(bot=bot)
        assert get_bot_user(repo) == bot

    def test_repo_bot_user_author_bot(self):
        bot = OwnerFactory()
        author = OwnerFactory(bot=bot)
        repo = RepositoryFactory(author=author)
        assert get_bot_user(repo) == bot

    def test_repo_bot_user_author(self):
        author = OwnerFactory()
        repo = RepositoryFactory(author=author)
        assert get_bot_user(repo) == author
