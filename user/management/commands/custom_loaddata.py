from django.core.management.base import BaseCommand
from django.core.serializers import deserialize
from django.db import transaction, IntegrityError
from tqdm import tqdm  # pip install tqdm

class Command(BaseCommand):
    help = 'Custom loaddata with progress and error logging'

    def add_arguments(self, parser):
        parser.add_argument('fixture', type=str, help='Fixture file path')

    def handle(self, *args, **options):
        fixture_path = options['fixture']
        skipped = []

        with open(fixture_path, 'r', encoding='utf-8') as f:
            objects = list(deserialize('json', f))
            total = len(objects)

        self.stdout.write(self.style.NOTICE(f"Loading {total} objects from {fixture_path}..."))

        for i, obj in enumerate(tqdm(objects, desc="Loading objects")):
            try:
                with transaction.atomic():
                    obj.save()
            except IntegrityError as e:
                skipped.append((i, obj.object.__class__.__name__, str(e)))
                self.stderr.write(self.style.ERROR(
                    f"Skipped object #{i + 1} ({obj.object.__class__.__name__}): {e}"
                ))
            except Exception as e:
                skipped.append((i, obj.object.__class__.__name__, str(e)))
                self.stderr.write(self.style.ERROR(
                    f"Unexpected error on object #{i + 1} ({obj.object.__class__.__name__}): {e}"
                ))

        self.stdout.write(self.style.SUCCESS(f"\nDone! Loaded {total - len(skipped)} out of {total} objects."))

        if skipped:
            self.stdout.write(self.style.WARNING("\nSkipped objects summary:"))
            for i, model, err in skipped:
                self.stdout.write(f" - #{i + 1} {model}: {err}")
