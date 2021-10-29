from ariadne import ObjectType

from graphql_api.types.enums.enums import GoalOnboarding, TypeProjectOnboarding

profile_bindable = ObjectType("Profile")


@profile_bindable.field("goals")
def resolve_goals(profile, _):
    return [GoalOnboarding(goal) for goal in profile.goals]


@profile_bindable.field("typeProjects")
def resolve_type_projects(profile, _):
    return [TypeProjectOnboarding(project) for project in profile.type_projects]
