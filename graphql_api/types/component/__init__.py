from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .component import component_bindable

component = ariadne_load_local_graphql(__file__, "component.graphql")
