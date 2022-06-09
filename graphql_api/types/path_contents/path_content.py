from ariadne import ObjectType

path_content_bindable = ObjectType("PathContent")

@path_content_bindable.field("name")
def resolve_name(data, info):
    return data.name


@path_content_bindable.field("filePath")
def resolve_(data, info):
    if data.kind == "file":
        return data.full_path
    return None


@path_content_bindable.field("percentCovered")
def resolve_content(data, info):
    return data.coverage


@path_content_bindable.field("type")
def resolve_type(data, info):
    return data.kind
