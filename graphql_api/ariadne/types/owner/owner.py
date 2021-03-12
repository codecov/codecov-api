from ariadne import ObjectType

from graphql_api.helpers import ariadne_load_local_graphql

owner = ariadne_load_local_graphql(__file__, "owner.graphql")
owner_bindable = ObjectType("Owner")
