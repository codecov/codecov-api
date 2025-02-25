import csv

from django.core.management.base import BaseCommand
from shared.django_apps.codecov_auth.models import Plan, Tier


class Command(BaseCommand):
    help = "Insert data from a CSV file into the database for either plans or tiers"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="The path to the CSV file")
        parser.add_argument(
            "--model",
            type=str,
            choices=["plans", "tiers"],
            required=True,
            help="Specify the model to insert data into: plans or tiers",
        )

    def handle(self, *args, **kwargs):
        csv_file_path = kwargs["csv_file"]
        model_choice = kwargs["model"]

        # Determine which model to use
        if model_choice == "plans":
            Model = Plan
        elif model_choice == "tiers":
            Model = Tier
        else:
            self.stdout.write(self.style.ERROR("Invalid model choice"))
            return

        with open(csv_file_path, newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                model_data = {
                    field: self.convert_value(value)
                    for field, value in row.items()
                    if field in [f.name for f in Model._meta.fields]
                }

                # Handle ForeignKey for tier
                if "tier_id" in row and model_choice == "plans":
                    try:
                        model_data["tier"] = Tier.objects.get(id=row["tier_id"])
                    except Tier.DoesNotExist:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Tier with id {row['tier_id']} does not exist. Skipping row."
                            )
                        )
                        continue

                try:
                    Model.objects.update_or_create(
                        defaults=model_data,
                        id=row.get("id"),
                    )
                    self.stdout.write(self.style.SUCCESS(f"Inserted row: {row}"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error inserting row: {e}"))
                    continue

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully inserted all data into {model_choice} from CSV"
            )
        )

    def convert_value(self, value):
        """Convert CSV string values to appropriate Python types."""
        if value == "":
            return None
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        return value
