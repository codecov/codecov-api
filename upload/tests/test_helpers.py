from core.tests.factories import OwnerFactory, RepositoryFactory
from upload.helpers import try_to_get_best_possible_bot_token


def test_try_to_get_best_possible_bot_token_no_repobot_no_ownerbot(db):
    owner = OwnerFactory.create(unencrypted_oauth_token="super")
    owner.save()
    repository = RepositoryFactory.create(author=owner)
    repository.save()
    assert try_to_get_best_possible_bot_token(repository) == {
        "key": "super",
        "secret": None,
    }


def test_try_to_get_best_possible_bot_token_no_repobot_yes_ownerbot(db):
    bot = OwnerFactory.create(unencrypted_oauth_token="bornana")
    bot.save()
    owner = OwnerFactory.create(unencrypted_oauth_token="super", bot=bot)
    owner.save()
    repository = RepositoryFactory.create(author=owner)
    repository.save()
    assert try_to_get_best_possible_bot_token(repository) == {
        "key": "bornana",
        "secret": None,
    }


def test_try_to_get_best_possible_bot_token_yes_repobot(db):
    bot = OwnerFactory.create(unencrypted_oauth_token="bornana")
    bot.save()
    another_bot = OwnerFactory.create(unencrypted_oauth_token="anotha_one")
    another_bot.save()
    owner = OwnerFactory.create(unencrypted_oauth_token="super", bot=bot)
    owner.save()
    repository = RepositoryFactory.create(author=owner, bot=another_bot)
    repository.save()
    assert try_to_get_best_possible_bot_token(repository) == {
        "key": "anotha_one",
        "secret": None,
    }


def test_try_to_get_best_possible_nothing_and_is_private(db):
    owner = OwnerFactory.create(oauth_token=None)
    owner.save()
    repository = RepositoryFactory.create(author=owner, bot=None, private=True)
    repository.save()
    assert try_to_get_best_possible_bot_token(repository) is None


def test_try_to_get_best_possible_nothing_and_not_private(db, mocker):
    something = mocker.MagicMock()
    mock_get_config = mocker.patch("upload.helpers.get_config", return_value=something)
    owner = OwnerFactory.create(service="github", oauth_token=None)
    owner.save()
    repository = RepositoryFactory.create(author=owner, bot=None, private=False)
    repository.save()
    assert try_to_get_best_possible_bot_token(repository) is something
    mock_get_config.assert_called_with("github", "bot")
