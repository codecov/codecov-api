import yaml
from ariadne import ObjectType

comparison_bindable = ObjectType("Comparison")


@comparison_bindable.field("impactedFiles")
def resolve_impacted_files(comparison, info):
    command = info.context["executor"].get_command("compare")
    return command.get_impacted_files(comparison)
