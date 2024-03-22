from graphql_api.helpers.ariadne import ariadne_load_local_graphql
from graphql_api.helpers.connection import build_connection_graphql

from .component import component_bindable

component = ariadne_load_local_graphql(__file__, "component.graphql")
component += build_connection_graphql(
    "ComponentMeasurementsConnection", "ComponentMeasurements"
)
