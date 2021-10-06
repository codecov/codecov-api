from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .profile import profile_bindable

profile = ariadne_load_local_graphql(__file__, "profile.graphql")
