from shelf.models import Category, Product, Sizes
from cart.models import Cart

def Context(request):
    category = Category.objects.all()
    sizes = Sizes.objects.all()

    for cat in category:
        cat.count = Product.objects.filter(categories=cat).count()

    # Get the cart for logged-in users or anonymous users
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user, cleared=False)
    else:
        # Use session-based cart for anonymous users
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
        cart, created = Cart.objects.get_or_create(session_id=request.session.session_key, cleared=False)

    context = {
        'category': category,
        'all_sizes': sizes,
        'cart': cart,
        'cart_items': cart.cartitem_set.all()  # Retrieve cart items
    }
    return context
