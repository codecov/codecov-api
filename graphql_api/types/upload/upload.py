from datetime import datetime

from ariadne import ObjectType
from asgiref.sync import sync_to_async

upload_bindable = ObjectType("Upload")
upload_bindable.set_alias("flags", "flag_names")
