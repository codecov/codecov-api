from .aggregates import run_sql as aggregates_run_sql
from .array_append_unique import run_sql as array_append_unique_run_sql
from .coverage import run_sql as coverage_run_sql
from .get_access_token import run_sql as get_access_token_run_sql
from .get_author import run_sql as get_author_run_sql
from .get_commit import run_sql as get_commit_run_sql
from .get_customer import run_sql as get_customer_run_sql
from .get_graph_for import run_sql as get_graph_for_run_sql
from .get_ownerid import run_sql as get_ownerid_run_sql
from .get_repo import run_sql as get_repo_run_sql
from .get_user import run_sql as get_user_run_sql
from .insert_commit import run_sql as insert_commit_run_sql
from .refresh_repos import run_sql as refresh_repos_run_sql
from .update_json import run_sql as update_json_run_sql
from .verify_session import run_sql as verify_session_run_sql


def run_sql(schema_editor):
    aggregates_run_sql(schema_editor)
    update_json_run_sql(schema_editor)
    get_author_run_sql(schema_editor)
    array_append_unique_run_sql(schema_editor)
    coverage_run_sql(schema_editor)
    get_access_token_run_sql(schema_editor)
    get_repo_run_sql(schema_editor)
    get_user_run_sql(schema_editor)
    get_customer_run_sql(schema_editor)
    get_commit_run_sql(schema_editor)
    get_ownerid_run_sql(schema_editor)
    verify_session_run_sql(schema_editor)
    refresh_repos_run_sql(schema_editor)
    insert_commit_run_sql(schema_editor)
    get_graph_for_run_sql(schema_editor)
