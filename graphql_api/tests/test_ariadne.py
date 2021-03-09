from django.test import TestCase
from ariadne import graphql_sync

from graphql_api.ariadne import schema

class ArianeTestCase(TestCase):

    def test_hello_world(self):
        response = self.client.post('/graphql/ariadne', {
            "query": "{ hello }"
        }, content_type="application/json")
        assert response.status_code == 200
        assert response.json()['data'] == {'hello': 'hi'}
