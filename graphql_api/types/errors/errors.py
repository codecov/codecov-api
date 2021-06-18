from ariadne import ObjectType

unauthenticated_bindable = ObjectType("UnauthenticatedError")


@unauthenticated_bindable.field("message")
def resolve_error(err, info):
    return "bro lol putain"
