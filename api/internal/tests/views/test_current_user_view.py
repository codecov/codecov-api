from django.utils import timezone
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from shared.django_apps.codecov_auth.tests.factories import OwnerFactory, UserFactory


class CurrentUserViewTests(APITestCase):
    def setUp(self):
        self.user = UserFactory(terms_agreement=True, terms_agreement_at=timezone.now())
        self.owner1 = OwnerFactory(user=self.user)
        self.owner2 = OwnerFactory(user=self.user)
        self.owner3 = OwnerFactory()

    def test_current_user_unauthenticated(self):
        res = self.client.get(reverse("current-user"))
        assert res.status_code == 401

    def test_current_user_authenticated(self):
        self.client.force_login(self.user)
        res = self.client.get(reverse("current-user"))
        assert res.status_code == 200
        data = res.data
        ownerids = [owner["ownerid"] for owner in data.pop("owners")]
        assert data == {
            "email": self.user.email,
            "name": self.user.name,
            "external_id": str(self.user.external_id),
            "terms_agreement": self.user.terms_agreement,
            "terms_agreement_at": self.user.terms_agreement_at.strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
        }
        assert len(ownerids) == 2
        assert self.owner1.ownerid in ownerids
        assert self.owner2.ownerid in ownerids
        assert self.owner3.ownerid not in ownerids
