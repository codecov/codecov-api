from ariadne import MutationType

from .activate_measurements import (
    error_activate_measurements,
    resolve_activate_measurements,
)
from .cancel_trial import error_cancel_trial, resolve_cancel_trial
from .create_api_token import error_create_api_token, resolve_create_api_token
from .create_stripe_setup_intent import (
    error_create_stripe_setup_intent,
    resolve_create_stripe_setup_intent,
)
from .create_user_token import error_create_user_token, resolve_create_user_token
from .delete_component_measurements import (
    error_delete_component_measurements,
    resolve_delete_component_measurements,
)
from .delete_flag import error_delete_flag, resolve_delete_flag
from .delete_session import error_delete_session, resolve_delete_session
from .encode_secret_string import (
    error_encode_secret_string,
    resolve_encode_secret_string,
)
from .erase_repository import error_erase_repository, resolve_erase_repository
from .onboard_user import error_onboard_user, resolve_onboard_user
from .regenerate_org_upload_token import (
    error_generate_org_upload_token,
    resolve_regenerate_org_upload_token,
)
from .regenerate_repository_token import (
    error_regenerate_repository_token,
    resolve_regenerate_repository_token,
)
from .regenerate_repository_upload_token import (
    error_regenerate_repository_upload_token,
    resolve_regenerate_repository_upload_token,
)
from .revoke_user_token import error_revoke_user_token, resolve_revoke_user_token
from .save_okta_config import error_save_okta_config, resolve_save_okta_config
from .save_sentry_state import error_save_sentry_state, resolve_save_sentry_state
from .save_terms_agreement import (
    error_save_terms_agreement,
    resolve_save_terms_agreement,
)
from .set_upload_token_required import (
    error_set_upload_token_required,
    resolve_set_upload_token_required,
)
from .set_yaml_on_owner import error_set_yaml_error, resolve_set_yaml_on_owner
from .start_trial import error_start_trial, resolve_start_trial
from .store_event_metrics import error_store_event_metrics, resolve_store_event_metrics
from .sync_with_git_provider import (
    error_sync_with_git_provider,
    resolve_sync_with_git_provider,
)
from .update_bundle_cache_config import (
    error_update_bundle_cache_config,
    resolve_update_bundle_cache_config,
)
from .update_default_organization import (
    error_update_default_organization,
    resolve_update_default_organization,
)
from .update_profile import error_update_profile, resolve_update_profile
from .update_repository import error_update_repository, resolve_update_repository
from .update_self_hosted_settings import (
    error_update_self_hosted_settings,
    resolve_update_self_hosted_settings,
)

mutation_bindable = MutationType()

# Here, bind the resolvers from each subfolder to the Mutation type
mutation_bindable.field("createApiToken")(resolve_create_api_token)
mutation_bindable.field("createStripeSetupIntent")(resolve_create_stripe_setup_intent)
mutation_bindable.field("createUserToken")(resolve_create_user_token)
mutation_bindable.field("revokeUserToken")(resolve_revoke_user_token)
mutation_bindable.field("setYamlOnOwner")(resolve_set_yaml_on_owner)
mutation_bindable.field("syncWithGitProvider")(resolve_sync_with_git_provider)
mutation_bindable.field("deleteSession")(resolve_delete_session)
mutation_bindable.field("updateProfile")(resolve_update_profile)
mutation_bindable.field("updateDefaultOrganization")(
    resolve_update_default_organization
)
mutation_bindable.field("onboardUser")(resolve_onboard_user)
mutation_bindable.field("regenerateRepositoryToken")(
    resolve_regenerate_repository_token
)
mutation_bindable.field("activateMeasurements")(resolve_activate_measurements)
mutation_bindable.field("regenerateOrgUploadToken")(resolve_regenerate_org_upload_token)
mutation_bindable.field("deleteFlag")(resolve_delete_flag)
mutation_bindable.field("saveSentryState")(resolve_save_sentry_state)
mutation_bindable.field("saveTermsAgreement")(resolve_save_terms_agreement)
mutation_bindable.field("startTrial")(resolve_start_trial)
mutation_bindable.field("cancelTrial")(resolve_cancel_trial)
mutation_bindable.field("deleteComponentMeasurements")(
    resolve_delete_component_measurements
)
mutation_bindable.field("eraseRepository")(resolve_erase_repository)
mutation_bindable.field("updateRepository")(resolve_update_repository)
mutation_bindable.field("updateSelfHostedSettings")(resolve_update_self_hosted_settings)
mutation_bindable.field("regenerateRepositoryUploadToken")(
    resolve_regenerate_repository_upload_token
)
mutation_bindable.field("encodeSecretString")(resolve_encode_secret_string)

mutation_bindable.field("storeEventMetric")(resolve_store_event_metrics)

mutation_bindable.field("saveOktaConfig")(resolve_save_okta_config)
mutation_bindable.field("setUploadTokenRequired")(resolve_set_upload_token_required)
mutation_bindable.field("updateBundleCacheConfig")(resolve_update_bundle_cache_config)

mutation_resolvers = [
    mutation_bindable,
    error_create_api_token,
    error_create_stripe_setup_intent,
    error_create_user_token,
    error_revoke_user_token,
    error_set_yaml_error,
    error_sync_with_git_provider,
    error_delete_session,
    error_update_profile,
    error_update_default_organization,
    error_onboard_user,
    error_regenerate_repository_token,
    error_activate_measurements,
    error_generate_org_upload_token,
    error_delete_component_measurements,
    error_delete_flag,
    error_save_sentry_state,
    error_save_terms_agreement,
    error_start_trial,
    error_cancel_trial,
    error_erase_repository,
    error_update_repository,
    error_update_self_hosted_settings,
    error_regenerate_repository_upload_token,
    error_encode_secret_string,
    error_store_event_metrics,
    error_save_okta_config,
    error_set_upload_token_required,
    error_update_bundle_cache_config,
]
