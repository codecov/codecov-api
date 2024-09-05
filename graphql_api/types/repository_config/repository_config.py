from typing import TypedDict

from ariadne import ObjectType
from shared.yaml.user_yaml import UserYaml

from codecov.db import sync_to_async
from core.models import Repository
from graphql_api.dataloader.owner import OwnerLoader

repository_config_bindable = ObjectType("RepositoryConfig")
indication_range_bindable = ObjectType("IndicationRange")


class IndicationRange(TypedDict):
    lowerRange: float
    upperRange: float


@repository_config_bindable.field("indicationRange")
async def resolve_indication_range(repository: Repository, info) -> dict[str, float]:
    owner = await OwnerLoader.loader(info).load(repository.author_id)

    yaml = await sync_to_async(UserYaml.get_final_yaml)(
        owner_yaml=owner.yaml, repo_yaml=repository.yaml
    )
    range: list[float] = yaml.get("coverage", {"range": [60, 80]}).get(
        "range", [60, 80]
    )
    return {"lowerRange": range[0], "upperRange": range[1]}


@indication_range_bindable.field("upperRange")
def resolve_upper_range(indicationRange: IndicationRange, info) -> float:
    upperRange = indicationRange.get("upperRange")
    return upperRange


@indication_range_bindable.field("lowerRange")
def resolve_lower_range(indicationRange: IndicationRange, info) -> float:
    lowerRange = indicationRange.get("lowerRange")
    return lowerRange
