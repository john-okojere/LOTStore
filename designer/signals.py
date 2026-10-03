from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .views import claim_guest_designs


@receiver(user_logged_in)
def claim_designs_on_login(sender, request, user, **kwargs):
    """Move drafts a visitor made before signing in into their account."""
    if request is not None and hasattr(request, "session"):
        claim_guest_designs(request, user)
