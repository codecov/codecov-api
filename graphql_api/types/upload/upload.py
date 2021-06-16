from ariadne import ObjectType


upload_bindable = ObjectType("Upload")


@upload_bindable.field("state")
def resolve_state(upload, info):
    return "SUCCESS"


@upload_bindable.field("provider")
def resolve_state(upload, info):
    return "CIRCLE"


@upload_bindable.field("createdAt")
def resolve_state(upload, info):
    return None
