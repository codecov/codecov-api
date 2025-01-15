from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .activate_measurements import gql_activate_measurements
from .cancel_trial import gql_cancel_trial
from .create_api_token import gql_create_api_token
from .create_stripe_setup_intent import gql_create_stripe_setup_intent
from .create_user_token import gql_create_user_token
from .delete_component_measurements import gql_delete_component_measurements
from .delete_flag import gql_delete_flag
from .delete_session import gql_delete_session
from .encode_secret_string import gql_encode_secret_string
from .erase_repository import gql_erase_repository
from .mutation import mutation_resolvers  # noqa: F401
from .onboard_user import gql_onboard_user
from .regenerate_org_upload_token import gql_regenerate_org_upload_token
from .regenerate_repository_token import gql_regenerate_repository_token
from .regenerate_repository_upload_token import gql_regenerate_repository_upload_token
from .revoke_user_token import gql_revoke_user_token
from .save_okta_config import gql_save_okta_config
from .save_sentry_state import gql_save_sentry_state
from .save_terms_agreement import gql_save_terms_agreement
from .set_upload_token_required import gql_set_upload_token_required
from .set_yaml_on_owner import gql_set_yaml_on_owner
from .start_trial import gql_start_trial
from .store_event_metrics import gql_store_event_metrics
from .sync_with_git_provider import gql_sync_with_git_provider
from .update_bundle_cache_config import gql_update_bundle_cache_config
from .update_default_organization import gql_update_default_organization
from .update_profile import gql_update_profile
from .update_repository import gql_update_repository
from .update_self_hosted_settings import gql_update_self_hosted_settings

mutation = ariadne_load_local_graphql(__file__, "mutation.graphql")
mutation = mutation + gql_create_api_token
mutation = mutation + gql_create_stripe_setup_intent
mutation = mutation + gql_sync_with_git_provider
mutation = mutation + gql_delete_session
mutation = mutation + gql_set_yaml_on_owner
mutation = mutation + gql_update_profile
mutation = mutation + gql_update_default_organization
mutation = mutation + gql_onboard_user
mutation = mutation + gql_regenerate_repository_token
mutation = mutation + gql_activate_measurements
mutation = mutation + gql_regenerate_org_upload_token
mutation = mutation + gql_create_user_token
mutation = mutation + gql_revoke_user_token
mutation = mutation + gql_delete_flag
mutation = mutation + gql_save_sentry_state
mutation = mutation + gql_save_terms_agreement
mutation = mutation + gql_start_trial
mutation = mutation + gql_cancel_trial
mutation = mutation + gql_delete_component_measurements
mutation = mutation + gql_erase_repository
mutation = mutation + gql_update_repository
mutation = mutation + gql_update_self_hosted_settings
mutation = mutation + gql_regenerate_repository_upload_token
mutation = mutation + gql_encode_secret_string
mutation = mutation + gql_store_event_metrics
mutation = mutation + gql_save_okta_config
mutation = mutation + gql_set_upload_token_required
mutation = mutation + gql_update_bundle_cache_config
