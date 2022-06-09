from ariadne import ObjectType

tree_file_bindable = ObjectType("TreeFile")

@tree_file_bindable.field("name")
def resolve_name(data, info):
    return data["name"]

@tree_file_bindable.field("filePath")
def resolve_(data, info):
    if data["type"] == "file":
        return data["full_path"]
    return None

@tree_file_bindable.field("percentCovered")
def resolve_content(data, info):
    return data["coverage"]

@tree_file_bindable.field("type")
def resolve_type(data, info):
    return data["type"]