import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F, Sum
from django.db.models.functions import Greatest
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags
from django.views.decorators.http import require_POST

from shelf.models import Product, Sizes

from .forms import AddToCartForm, CheckoutForm
from .models import Cart, CartItem, Order, Payment

logger = logging.getLogger(__name__)

SESSION_CART_KEY = 'cart_id'


def _ensure_session(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _get_active_cart(request, create=True):
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user, cleared=False).order_by('-id').first()
        if cart is None and create:
            cart = Cart.objects.create(user=request.user)
        return cart

    session_key = _ensure_session(request)
    cart = Cart.objects.filter(session_id=session_key, cleared=False).order_by('-id').first()
    if cart is None and create:
        cart = Cart.objects.create(session_id=session_key)
    if cart is not None:
        # Remembered in session data so the cart survives the session key
        # rotation that happens on login (see cart.signals).
        request.session[SESSION_CART_KEY] = cart.pk
    return cart


def _can_access_cart(request, cart):
    if request.user.is_authenticated:
        return cart.user_id == request.user.id
    session_key = _ensure_session(request)
    return bool(cart.session_id and cart.session_id == session_key)


def _can_access_payment(request, payment):
    if request.user.is_staff:
        return True
    if request.user.is_authenticated:
        return payment.user_id == request.user.id
    session_key = _ensure_session(request)
    return bool(payment.session_id and payment.session_id == session_key)


def _cart_items(cart):
    return cart.cartitem_set.select_related('product').prefetch_related('size')


def _cart_total(cart):
    return sum(item.subtotal() for item in cart.cartitem_set.select_related('product'))


def _quantity_in_cart(cart, product, exclude_item=None):
    items = CartItem.objects.filter(cart=cart, product=product)
    if exclude_item is not None:
        items = items.exclude(pk=exclude_item.pk)
    return items.aggregate(total=Sum('quantity'))['total'] or 0


def _stock_problems(cart_items):
    """Return a message for every product whose cart quantity exceeds stock."""
    wanted = {}
    for item in cart_items:
        entry = wanted.setdefault(item.product_id, [item.product, 0])
        entry[1] += item.quantity
    problems = []
    for product, quantity in wanted.values():
        if product.stock <= 0:
            problems.append(f'{product.name} is out of stock.')
        elif quantity > product.stock:
            problems.append(f'Only {product.stock} of {product.name} left in stock (you have {quantity}).')
    return problems


def _get_or_create_matching_item(cart, product, info, size_ids):
    if not size_ids:
        item, _ = CartItem.objects.get_or_create(cart=cart, product=product, info=info)
        return item

    selected_ids = sorted(size_ids)
    candidates = CartItem.objects.filter(cart=cart, product=product, info=info).prefetch_related('size')
    for item in candidates:
        if sorted(item.size.values_list('id', flat=True)) == selected_ids:
            return item

    item = CartItem.objects.create(cart=cart, product=product, info=info)
    item.size.set(Sizes.objects.filter(id__in=selected_ids))
    return item


def _first_error(form):
    for errors in form.errors.values():
        if errors:
            return errors[0]
    return 'Please check your input and try again.'


@require_POST
def add_to_cart(request, product_uid):
    product = get_object_or_404(Product, uid=product_uid, is_public=True)

    form = AddToCartForm(request.POST, product=product)
    if not form.is_valid():
        return JsonResponse({'success': False, 'message': _first_error(form), 'errors': form.errors}, status=400)

    quantity = form.cleaned_data['quantity']
    if product.productType == 'Single Buy':
        quantity = 1
    info = form.cleaned_data.get('info', '')
    size_ids = [
        int(key.split('_')[1])
        for key, value in form.cleaned_data.items()
        if key.startswith('size_') and value
    ]

    if product.stock <= 0:
        return JsonResponse({'success': False, 'message': f'{product.name} is out of stock.'}, status=400)

    cart = _get_active_cart(request, create=True)
    if _quantity_in_cart(cart, product) + quantity > product.stock:
        return JsonResponse(
            {'success': False, 'message': f'Only {product.stock} of {product.name} available.'},
            status=400,
        )

    cart_item = _get_or_create_matching_item(cart, product, info, size_ids)
    cart_item.quantity += quantity
    cart_item.save()

    if size_ids:
        cart_item.size.set(Sizes.objects.filter(id__in=size_ids))

    return JsonResponse(
        {
            'success': True,
            'message': 'Product added to cart successfully.',
            'cart_count': cart.cartitem_set.count(),
        }
    )


@require_POST
def delete_from_cart(request, cart_item_uid):
    cart_item = get_object_or_404(CartItem, uid=cart_item_uid)
    if not _can_access_cart(request, cart_item.cart):
        return HttpResponseForbidden('You are not allowed to delete this item.')

    cart_item.delete()
    return redirect('view_cart')


def view_cart(request):
    cart = _get_active_cart(request, create=False)
    cart_items = _cart_items(cart) if cart else []
    total = sum(item.subtotal() for item in cart_items)
    return render(
        request,
        'cart/view_cart.html',
        {'cart_items': cart_items, 'total': total, 'cart': cart, 'stock_problems': _stock_problems(cart_items)},
    )


@require_POST
def update_cart_quantity(request, cart_item_uid, action):
    cart_item = get_object_or_404(CartItem.objects.select_related('product'), uid=cart_item_uid)
    cart = cart_item.cart
    product = cart_item.product

    if not _can_access_cart(request, cart):
        return JsonResponse({'success': False, 'message': 'Forbidden'}, status=403)

    if action == 'increase':
        if product.productType == 'Single Buy':
            return JsonResponse({'success': False, 'message': 'Only one of this item can be bought per order.'}, status=400)
        if _quantity_in_cart(cart, product) + 1 > product.stock:
            return JsonResponse({'success': False, 'message': f'Only {product.stock} of {product.name} available.'}, status=400)
        cart_item.quantity += 1
    elif action == 'decrease':
        minimum = product.minBuy if product.productType == 'Min. Buy' else 1
        if cart_item.quantity > max(minimum, 1):
            cart_item.quantity -= 1
        else:
            cart_item.delete()
            return JsonResponse(
                {'success': True, 'deleted': True, 'total': _cart_total(cart), 'cart_count': cart.cartitem_set.count()}
            )
    else:
        return JsonResponse({'success': False, 'message': 'Invalid action.'}, status=400)

    cart_item.save()
    return JsonResponse(
        {
            'success': True,
            'quantity': cart_item.quantity,
            'subtotal': cart_item.subtotal(),
            'total': _cart_total(cart),
            'cart_count': cart.cartitem_set.count(),
        }
    )


def _checkout_initial(request):
    if not request.user.is_authenticated:
        return {}
    user = request.user
    initial = {'email': user.email, 'full_name': user.full_name().strip(), 'phone_number': user.phone}
    about = getattr(user, 'aboutprofile', None)
    if about is not None:
        initial.update({'address': about.address, 'state': about.state})
    last_payment = Payment.objects.filter(user=user).exclude(address__isnull=True).first()
    if last_payment is not None:
        initial.update({
            'address': last_payment.address,
            'city': last_payment.city,
            'state': last_payment.state,
            'phone_number': last_payment.phone_number or initial['phone_number'],
        })
    return initial


def initiate_payment(request):
    cart = _get_active_cart(request, create=False)
    cart_items = list(_cart_items(cart)) if cart else []
    total = sum(item.subtotal() for item in cart_items)

    if not cart_items:
        return redirect('view_cart')

    stock_problems = _stock_problems(cart_items)

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid() and not stock_problems:
            payment_payload = dict(form.cleaned_data, amount=total, cart=cart)
            if request.user.is_authenticated:
                payment_payload['user'] = request.user
            else:
                payment_payload['session_id'] = _ensure_session(request)

            payment = Payment.objects.create(**payment_payload)
            context = {
                'payment': payment,
                'paystack_pub_key': settings.PAYSTACK_PUBLIC_KEY,
                'amount_value': payment.amount_value(),
                'amount_naira': payment.amount_value() / 100,
            }
            return render(request, 'make_payment.html', context)
    else:
        form = CheckoutForm(initial=_checkout_initial(request))

    return render(
        request,
        'payment.html',
        {'cart': cart, 'total': total, 'form': form, 'stock_problems': stock_problems},
    )


def sm(request):
    return redirect('/')


def _payment_context(payment):
    cart = payment.cart
    cart_items = _cart_items(cart)
    total = sum(item.subtotal() for item in cart_items)
    order = Order.objects.filter(payment=payment).first()
    return {'cart_items': cart_items, 'total': total, 'cart': cart, 'payment': payment, 'order': order}


def viewpayment(request, ref):
    payment = get_object_or_404(Payment, ref=ref)
    if not _can_access_payment(request, payment):
        return HttpResponseForbidden('You are not allowed to view this payment.')
    return render(request, 'success.html', _payment_context(payment))


def _complete_payment(payment):
    """Create the order exactly once for a verified payment.

    Returns (order, created). Locks the payment row so a double callback or
    page refresh can't clear the cart / reduce stock / email twice.
    """
    with transaction.atomic():
        locked = Payment.objects.select_for_update().get(pk=payment.pk)
        order = Order.objects.filter(payment=locked).first()
        if order is not None:
            return order, False

        cart = locked.cart
        cart.cleared = True
        cart.save(update_fields=['cleared'])
        for item in cart.cartitem_set.all():
            # The customer has already paid, so never block here; clamp at 0.
            Product.objects.filter(pk=item.product_id).update(
                stock=Greatest(F('stock') - item.quantity, 0)
            )
        order = Order.objects.create(payment=locked)
        # Custom quotes become paid exactly once alongside their idempotent order.
        from designer.models import DesignRequest
        DesignRequest.objects.filter(
            quote__quote_product__cartitem__cart=cart,
            status="quote_accepted",
        ).update(status="paid")
        return order, True


def _absolute(request, url):
    return request.build_absolute_uri(url)


def _send_order_emails(request, context):
    payment, order = context['payment'], context['order']
    for item in context['cart_items']:
        item.absolute_image_url = _absolute(request, item.product.image.url) if item.product.image else ''
        item.absolute_url = _absolute(request, reverse('details', args=[item.product.uid]))
    context = dict(
        context,
        payment_url=_absolute(request, reverse('payment_view', args=[payment.ref])),
        order_url=_absolute(request, reverse('order_detail', args=[order.id])),
    )
    sender = settings.DEFAULT_FROM_EMAIL
    messages_to_send = [
        ('Order Confirmation - LOT Store', 'order_confirmation_email.html', [payment.email]),
        (f'New Order Received ({payment.ref})', 'new_order_email.html', [sender]),
    ]
    for subject, template, recipients in messages_to_send:
        try:
            html = render_to_string(template, context)
            send_mail(subject, strip_tags(html), sender, recipients, html_message=html)
        except Exception:
            # The customer has paid; a mail outage must not turn this into an error page.
            logger.exception('Failed to send "%s" for payment %s', subject, payment.ref)


def verify_payment(request, ref):
    payment = get_object_or_404(Payment, ref=ref)
    if not _can_access_payment(request, payment):
        return HttpResponseForbidden('You are not allowed to verify this payment.')

    if not payment.verified:
        total = _cart_total(payment.cart)
        if payment.amount == total:
            payment.verify_payment()

    if payment.verified:
        order, created = _complete_payment(payment)
        context = _payment_context(payment)
        if created:
            _send_order_emails(request, context)
        return render(request, 'success.html', context)

    return render(request, 'success.html', _payment_context(payment))


@login_required
def payment_history(request):
    if request.user.is_staff:
        payments = Payment.objects.filter(verified=True)
    else:
        payments = Payment.objects.filter(verified=True, user=request.user)
    payments = payments.select_related('order')
    return render(request, 'payment_history.html', {'payments': payments})


def _staff_set_order_flag(request, ref, field):
    if not request.user.is_staff:
        return HttpResponseForbidden('Only staff can update delivery status.')
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

    payment = get_object_or_404(Payment, ref=ref, verified=True)
    order, _ = Order.objects.get_or_create(payment=payment)
    setattr(order, field, True)
    order.save(update_fields=[field])
    return render(request, 'success.html', _payment_context(payment))


@login_required
def sent_order(request, ref):
    return _staff_set_order_flag(request, ref, 'sent')


@login_required
def order_delivered(request, ref):
    return _staff_set_order_flag(request, ref, 'delivered')
