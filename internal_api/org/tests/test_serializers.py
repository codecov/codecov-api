from json import loads, dumps

from pathlib import Path

from internal_api.org.serializers import OwnerSerializer, OwnerListSerializer
from core.tests.factories import CommitFactory, RepositoryFactory
from codecov_auth.tests.factories import OwnerFactory
from archive.services import ArchiveService

current_file = Path(__file__)


class TestSerializers(object):

    def test_orgs_serializer(self, mocker, db, codecov_vcr):

        owner = OwnerFactory(
            username='Test Person 1',
            service='github',
            email='testperson1@codecov.io',
            cache={ 'stats': { 'repos': 2, 'members': 3 } }
        )

        owner_with_repo = OwnerFactory(
            username='Test Person 2',
            service='github',
            email='testperson2@codecov.io',
            cache={ 'stats': { 'repos': 2, 'members': 3 } }
        )

        repo = RepositoryFactory(author=owner_with_repo, active=True)

        org = OwnerFactory(
            username='codecov',
            service='github',
            email='info@codecov.io',
            cache={ 'stats': { 'repos': 2, 'members': 3 } }
        )

        owner_with_org = OwnerFactory(
            username='Test Person 3',
            service='github',
            email='testperson3@codecov.io',
            organizations=[org.ownerid],
            cache={ 'stats': { 'repos': 2, 'members': 3 } }
        )

        

        res_owner = OwnerSerializer(instance=owner).data
        res_owner_with_repo = OwnerSerializer(instance=owner_with_repo).data
        res_owner_with_org = OwnerListSerializer(instance=owner_with_org).data

        expected_result = {
            "ownerid": owner.ownerid,
            "service": owner.service,
            "username": owner.username,
            "name": owner.name,
            "email": owner.email,
            "stats": {
                "repos": 2,
                "members": 3
            },
            "active_repos": None
        }

        expected_result_with_repo = {
            "ownerid": owner_with_repo.ownerid,
            "service": owner_with_repo.service,
            "username": owner_with_repo.username,
            "name": owner_with_repo.name,
            "email": owner_with_repo.email,
            "stats": {
                "repos": 2,
                "members": 3
            },
            "active_repos": [
                {
                    "repoid": repo.repoid,
                    "name": repo.name
                }
            ]
        }

        expected_result_with_org = {
            "ownerid": owner_with_org.ownerid,
            "service": owner_with_org.service,
            "username": owner_with_org.username,
            "name": owner_with_org.name,
            "email": owner_with_org.email,
            "stats": {
                "repos": 2,
                "members": 3
            },
            "active_repos": None,
            "orgs": [
                {
                    'active_repos': None,
                    'email': org.email,
                    'name': org.name,
                    'ownerid': org.ownerid,
                    'service': org.service,
                    'stats': {'members': 3, 'repos': 2},
                    'username': org.username
                }
            ],
        }

        assert expected_result == loads(dumps(res_owner))
        assert expected_result_with_repo == loads(dumps(res_owner_with_repo))
        assert expected_result_with_org == loads(dumps(res_owner_with_org))
