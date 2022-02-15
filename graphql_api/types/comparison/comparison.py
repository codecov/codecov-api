from ariadne import ObjectType

comparison_bindable = ObjectType("Comparison")


@comparison_bindable.field("impactedFiles")
def resolve_impacted_files(comparison, info):
    command = info.context["executor"].get_command("compare")
    return command.get_impacted_files(comparison)


@comparison_bindable.field("changeWithParent")
def resolve_change_with_parent(comparison, info):
    command = info.context["executor"].get_command("compare")
    return command.change_with_parent(comparison)
