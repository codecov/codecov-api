import pytest

from utils.test_utils import TestMigrations


class Migration0046Test(TestMigrations):
    migrate_from = "0045_remove_ownerprofile_terms_agreement"
    migrate_to = "0046_dedupe_owner_admin_values"

    def setUpBeforeMigration(self, apps):
        owners = apps.get_model("codecov_auth", "Owner")

        self.owner_no_dupes = owners.objects.create(
            ownerid=1,
            service_id=1,
            service="github",
            admins=[1, 2, 3],
        )

        self.owner_null_admins = owners.objects.create(
            ownerid=2,
            service_id=2,
            service="github",
            admins=None,
        )

        self.owner_no_admins = owners.objects.create(
            ownerid=3,
            service_id=3,
            service="github",
            admins=[],
        )

        self.owner_one_dupe = owners.objects.create(
            ownerid=4,
            service_id=4,
            service="github",
            admins=[1, 1],
        )

        self.owner_multi_dupe = owners.objects.create(
            ownerid=5,
            service_id=5,
            service="github",
            admins=[1, 1, 2, 3, 3, 3, 4],
        )

        self.owner_multi_dupe_ordering = owners.objects.create(
            ownerid=6,
            service_id=6,
            service="github",
            admins=[3, 2, 1, 2, 3],
        )

    @pytest.mark.skip(
        reason="move to shared"
    )  # TODO move this test to live with auth models in shared
    def test_admins_deduped(self):
        owners = self.apps.get_model("codecov_auth", "Owner")

        owner = owners.objects.get(ownerid=self.owner_no_dupes.ownerid)
        assert owner.admins == [1, 2, 3]

        owner = owners.objects.get(ownerid=self.owner_null_admins.ownerid)
        assert owner.admins == []

        owner = owners.objects.get(ownerid=self.owner_no_admins.ownerid)
        assert owner.admins == []

        owner = owners.objects.get(ownerid=self.owner_one_dupe.ownerid)
        assert owner.admins == [1]

        owner = owners.objects.get(ownerid=self.owner_multi_dupe.ownerid)
        assert owner.admins == [1, 2, 3, 4]

        owner = owners.objects.get(ownerid=self.owner_multi_dupe_ordering.ownerid)
        assert owner.admins == [3, 2, 1]
