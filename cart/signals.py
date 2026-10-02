from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import Cart, CartItem


@receiver(user_logged_in)
def merge_guest_cart(sender, request, user, **kwargs):
    """Move items a visitor added before signing in into their account cart.

    login() rotates the session key, so the guest cart is found via the cart
    id stored in session data (see cart.views._get_active_cart).
    """
    if request is None or not hasattr(request, 'session'):
        return
    cart_id = request.session.pop('cart_id', None)
    if not cart_id:
        return

    guest_cart = Cart.objects.filter(pk=cart_id, user__isnull=True, cleared=False).first()
    if guest_cart is None:
        return

    if guest_cart.cartitem_set.exists():
        user_cart = Cart.objects.filter(user=user, cleared=False).order_by('-id').first()
        if user_cart is None:
            guest_cart.user = user
            guest_cart.session_id = None
            guest_cart.save(update_fields=['user', 'session_id'])
            return
        CartItem.objects.filter(cart=guest_cart).update(cart=user_cart)
    guest_cart.delete()
