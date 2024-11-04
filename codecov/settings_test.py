import os

from .settings_dev import *

ALLOWED_HOSTS = ["localhost"]
CORS_ALLOWED_ORIGINS = ["http://localhost:9000", "http://localhost"]
SHELTER_PUBSUB_PROJECT_ID = "test-project-id"
SHELTER_PUBSUB_SYNC_REPO_TOPIC_ID = "test-topic-id"

# Mock the Pub/Sub host for testing
# this prevents the pubsub SDK from trying to load credentials
os.environ["PUBSUB_EMULATOR_HOST"] = "localhost"

GRAPHQL_INTROSPECTION_ENABLED = True
