from .v440 import run_sql as v440_run_sql
from .v442 import run_sql as v442_run_sql
from .v443 import run_sql as v443_run_sql
from .v446 import run_sql as v446_run_sql
from .v447 import run_sql as v447_run_sql
from .v448 import run_sql as v448_run_sql
from .v449 import run_sql as v449_run_sql
from .v451 import run_sql as v451_run_sql
from .v452 import run_sql as v452_run_sql
from .v453 import run_sql as v453_run_sql
from .v454 import run_sql as v454_run_sql
from .v455 import run_sql as v455_run_sql
from .v461 import run_sql as v461_run_sql
from .v4410 import run_sql as v4410_run_sql
from .v4510 import run_sql as v4510_run_sql

UPGRADE_MIGRATIONS_BY_VERSION = (
    ((4, 4, 0), v440_run_sql),
    ((4, 4, 2), v442_run_sql),
    ((4, 4, 3), v443_run_sql),
    ((4, 4, 6), v446_run_sql),
    ((4, 4, 7), v447_run_sql),
    ((4, 4, 8), v448_run_sql),
    ((4, 4, 9), v449_run_sql),
    ((4, 4, 10), v4410_run_sql),
    ((4, 5, 1), v451_run_sql),
    ((4, 5, 2), v452_run_sql),
    ((4, 5, 3), v453_run_sql),
    ((4, 5, 4), v454_run_sql),
    ((4, 5, 5), v455_run_sql),
    ((4, 5, 10), v4510_run_sql),
    ((4, 6, 1), v461_run_sql),
)


def _version_normalize(version):
    return tuple(int(x or 0) for x in version.replace("v", "").split("."))


def run_sql(schema_editor, current_version):
    normalized_current_version = _version_normalize(current_version)
    upgrade_migration_index_to_start_from = None

    for idx, (upgrade_version, _) in enumerate(UPGRADE_MIGRATIONS_BY_VERSION):
        if upgrade_version > normalized_current_version:
            upgrade_migration_index_to_start_from = idx
            break

    if not upgrade_migration_index_to_start_from:
        return

    for (_, upgrade_migration) in UPGRADE_MIGRATIONS_BY_VERSION[
        upgrade_migration_index_to_start_from:
    ]:
        upgrade_migration(schema_editor)
