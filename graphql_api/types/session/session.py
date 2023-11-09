from ariadne import ObjectType

session_bindable = ObjectType("Session")


@session_bindable.field("lastFour")
def resolve_last_four(session, _) -> str:
    return str(session.token)[-4:]
