from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from pathlib import Path
import os

class Command(BaseCommand):
    help = "Uploads all local media files to the configured media storage (S3)"

    def handle(self, *args, **options):
        media_root = Path("media")
        if not media_root.exists():
            self.stdout.write(self.style.ERROR("No local media folder found."))
            return

        for root, dirs, files in os.walk(media_root):
            for file in files:
                local_path = Path(root) / file
                relative_path = local_path.relative_to(media_root)
                with open(local_path, "rb") as f:
                    default_storage.save(f"{relative_path}", f)
                    self.stdout.write(self.style.SUCCESS(f"Uploaded: {relative_path}"))
