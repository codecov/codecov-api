class GraphQLTestHelper:

    def gql_request(self, url, query):
        response = self.client.post(url, {
            "query": query
        }, content_type="application/json")
        return response.json()['data']


def paginate_connection(connection):
    return [edge['node'] for edge in connection['edges']]
