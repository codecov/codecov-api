from django.core.management.base import BaseCommand, CommandParser

from services.redis_configuration import get_redis_connection


class Command(BaseCommand):
    help = "This command is meant to delete all rate limit redis keys for either userId or ip."

    def add_arguments(self, parser: CommandParser) -> None:
        # This argument switches the command to "anonymous mode" deleting all the ip based keys
        parser.add_argument("--ip", type=bool)

    def handle(self, *args, **options):
        redis = get_redis_connection()

        path = "rl-user:*"
        if options["ip"]:
            path = "rl-ip:*"

        try:
            for key in redis.scan_iter(path):
                # -1 means the key has no expiry
                if redis.ttl(key) == -1:
                    print(f"Deleting key: {key.decode('utf-8')}")  # noqa: T201
                    redis.delete(key)
        except Exception as e:
            print("Error occurred when deleting redis keys")  # noqa: T201
            print(e)  # noqa: T201
