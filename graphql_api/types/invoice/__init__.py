from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .invoice import invoice_bindable

invoice = ariadne_load_local_graphql(__file__, "invoice.graphql")


__all__ = ["invoice_bindable"]
