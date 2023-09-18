from datetime import datetime

from utils.test_utils import TestMigrations


class Migration0042Test(TestMigrations):

    migrate_from = "0041_auto_20230918_1825"
    migrate_to = "0042_sync_user_terms_agreement"

    def setUpBeforeMigration(self, apps):
        owners = apps.get_model("codecov_auth", "Owner")
        users = apps.get_model("codecov_auth", "User")
        profiles = apps.get_model("codecov_auth", "OwnerProfile")
        self.now = datetime.now()

        self.profile_have_user_and_have_agreements = profiles.objects.create(
            owner=owners.objects.create(
                ownerid=1,
                service_id=1,
                service="github",
                user=users.objects.create(),  # user's agreement fields defaults to (False,null)
            ),
            terms_agreement=True,
            terms_agreement_at=self.now,
        )
        self.profile_have_user_and_no_agreements = profiles.objects.create(
            owner=owners.objects.create(
                ownerid=2,
                service_id=2,
                service="github",
                user=users.objects.create(),  # user's agreement fields defaults to (False,null)
            ),
            terms_agreement=False,
            terms_agreement_at=None,
        )
        self.profile_no_user_and_have_agreements = profiles.objects.create(
            owner=owners.objects.create(
                ownerid=3, service_id=3, service="github", user=None
            ),
            terms_agreement=True,
            terms_agreement_at=self.now,
        )
        self.profile_no_user_and_no_agreements = profiles.objects.create(
            owner=owners.objects.create(
                ownerid=4, service_id=4, service="github", user=None
            ),
            terms_agreement=False,
            terms_agreement_at=None,
        )

        self.owner_have_user_no_profile = owners.objects.create(
            ownerid=5,
            service_id=5,
            service="github",
            user=users.objects.create(),  # user's agreement fields defaults to (False,null)
        )

        self.owner_no_user_no_profile = owners.objects.create(
            ownerid=6,
            service_id=6,
            service="github",
        )

    def test_agreements_migrated(self):
        owners = self.apps.get_model("codecov_auth", "Owner")

        owner = owners.objects.get(
            ownerid=self.profile_have_user_and_have_agreements.owner.ownerid
        )
        assert (
            owner.user.terms_agreement
            == self.profile_have_user_and_have_agreements.terms_agreement
        )
        assert (
            owner.user.terms_agreement_at
            == self.profile_have_user_and_have_agreements.terms_agreement_at
        )

        owner = owners.objects.get(
            ownerid=self.profile_have_user_and_no_agreements.owner.ownerid
        )
        assert (
            owner.user.terms_agreement
            == self.profile_have_user_and_no_agreements.terms_agreement
        )
        assert (
            owner.user.terms_agreement_at
            == self.profile_have_user_and_no_agreements.terms_agreement_at
        )

        owner = owners.objects.get(
            ownerid=self.profile_no_user_and_have_agreements.owner.ownerid
        )
        assert owner.user == None

        owner = owners.objects.get(
            ownerid=self.profile_no_user_and_no_agreements.owner.ownerid
        )
        assert owner.user == None

        owner = owners.objects.get(ownerid=self.owner_have_user_no_profile.ownerid)
        assert not hasattr(owner, "profile")
        assert owner.user != None

        owner = owners.objects.get(ownerid=self.owner_no_user_no_profile.ownerid)
        assert not hasattr(owner, "profile")
        assert owner.user == None
