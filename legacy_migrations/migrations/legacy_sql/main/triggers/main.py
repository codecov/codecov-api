from .branches import run_sql as branches_run_sql
from .commits import run_sql as commits_run_sql
from .owners import run_sql as owners_run_sql
from .pulls import run_sql as pulls_run_sql
from .repos import run_sql as repos_run_sql


def run_sql(schema_editor):
    commits_run_sql(schema_editor)
    branches_run_sql(schema_editor)
    owners_run_sql(schema_editor)
    repos_run_sql(schema_editor)
    pulls_run_sql(schema_editor)
