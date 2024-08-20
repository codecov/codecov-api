from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .gamification import (
    Badge,
    BadgeCollection,
    Leaderboard,
    badge_bindable,
    leaderboard_bindable,
    leaderboard_data_bindable,
)

gamification = ariadne_load_local_graphql(__file__, "gamification.graphql")
