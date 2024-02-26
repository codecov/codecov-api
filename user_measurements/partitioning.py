from dateutil.relativedelta import relativedelta
from psqlextra.partitioning import (
    PostgresCurrentTimePartitioningStrategy,
    PostgresPartitioningManager,
    PostgresTimePartitionSize,
)
from psqlextra.partitioning.config import PostgresPartitioningConfig

from user_measurements.models import UserMeasurement

# Overlapping partitions will cause errors - https://www.postgresql.org/docs/current/ddl-partitioning.html#DDL-PARTITIONING-DECLARATIVE -> "create partitions"
manager = PostgresPartitioningManager(
    [
        # 6 partitions ahead, each partition is two month
        # Partitions can be deleted after 12 months of their starting date, not their creation, via the pgpartition command.
        # They won't be automatically deleted though.
        # Partitions will be named `[table_name]_[year]_[3-letter month name]`.
        PostgresPartitioningConfig(
            model=UserMeasurement,
            strategy=PostgresCurrentTimePartitioningStrategy(
                size=PostgresTimePartitionSize(months=2),
                count=6,
                max_age=relativedelta(months=12),
            ),
        ),
    ]
)
