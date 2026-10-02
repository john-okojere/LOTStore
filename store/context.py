from shelf.models import Category, Sizes
from cart.models import Cart
from django.db.models import Count

def Context(request):
    category = Category.objects.annotate(count=Count('product', distinct=True))
    sizes = Sizes.objects.all()

    # Look up the active cart without creating one: creating a session and a
    # Cart row on every page view (including bots/crawlers) bloats the database.
    # Carts are created on demand when an item is added (see cart.views).
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user, cleared=False).first()
    elif request.session.session_key:
        cart = Cart.objects.filter(session_id=request.session.session_key, cleared=False).first()
    else:
        cart = None

    context = {
        'category': category,
        'all_sizes': sizes,
        'cart': cart,
        'cart_items': cart.cartitem_set.select_related('product').all() if cart else [],
    }
    return context
