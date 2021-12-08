from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .upload import upload_bindable, upload_error_bindable

upload = ariadne_load_local_graphql(__file__, "upload.graphql")
