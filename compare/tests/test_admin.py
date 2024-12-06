from django.test import TestCase
from django.urls import reverse
from shared.django_apps.codecov_auth.tests.factories import UserFactory

from .factories import CommitComparisonFactory


class CompareAdminTest(TestCase):
    def setUp(self):
        # Create a couple of comparison so the list has something to display
        CommitComparisonFactory()
        CommitComparisonFactory()
        self.staff_user = UserFactory(is_staff=True)
        self.client.force_login(user=self.staff_user)

    def test_compare_admin_detail_page(self):
        response = self.client.get(reverse("admin:compare_commitcomparison_changelist"))
        self.assertEqual(response.status_code, 200)
