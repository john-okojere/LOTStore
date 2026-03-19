from shelf.models import Category, Sizes
from cart.models import Cart
from django.db.models import Count

def Context(request):
    category = Category.objects.annotate(count=Count('product', distinct=True))
    sizes = Sizes.objects.all()

    # Get the cart for logged-in users or anonymous users
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user, cleared=False)
    else:
        # Use session-based cart for anonymous users
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
        cart, _ = Cart.objects.get_or_create(session_id=request.session.session_key, cleared=False)

    context = {
        'category': category,
        'all_sizes': sizes,
        'cart': cart,
        'cart_items': cart.cartitem_set.select_related('product').all()
    }
    return context
