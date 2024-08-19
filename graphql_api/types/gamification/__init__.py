from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .gamification import Leaderboard, leaderboard_bindable, leaderboard_data_bindable

gamification = ariadne_load_local_graphql(__file__, "gamification.graphql")
