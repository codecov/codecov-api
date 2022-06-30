from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .measurement import measurement_bindable

measurement = ariadne_load_local_graphql(__file__, "measurement.graphql")
