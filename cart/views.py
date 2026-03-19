from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from shelf.models import Product, Sizes

from .forms import AddToCartForm
from .models import Cart, CartItem, Order, Payment


def _ensure_session(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _get_active_cart(request, create=True):
    if request.user.is_authenticated:
        if create:
            cart, _ = Cart.objects.get_or_create(user=request.user, cleared=False)
            return cart
        return Cart.objects.filter(user=request.user, cleared=False).first()

    session_key = _ensure_session(request)
    if create:
        cart, _ = Cart.objects.get_or_create(session_id=session_key, cleared=False)
        return cart
    return Cart.objects.filter(session_id=session_key, cleared=False).first()


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


def add_to_cart(request, product_uid):
    product = get_object_or_404(Product, uid=product_uid)

    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

    form = AddToCartForm(request.POST, product=product)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    quantity = form.cleaned_data['quantity']
    info = form.cleaned_data.get('info', '')
    size_ids = [
        int(key.split('_')[1])
        for key, value in form.cleaned_data.items()
        if key.startswith('size_') and value
    ]

    if len(size_ids) > 1 and quantity == 1:
        return JsonResponse(
            {
                'success': False,
                'errors': 'You cannot select more than one size if the quantity is one.',
            },
            status=400,
        )

    cart = _get_active_cart(request, create=True)
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


def delete_from_cart(request, cart_item_uid):
    cart_item = get_object_or_404(CartItem, uid=cart_item_uid)
    if not _can_access_cart(request, cart_item.cart):
        return HttpResponseForbidden('You are not allowed to delete this item.')

    cart_item.delete()
    return redirect('view_cart')


def view_cart(request):
    cart = _get_active_cart(request, create=True)
    cart_items = cart.cartitem_set.select_related('product').all()
    total = sum(item.subtotal() for item in cart_items)
    return render(request, 'cart/view_cart.html', {'cart_items': cart_items, 'total': total, 'cart': cart})


def update_cart_quantity(request, cart_item_uid, action):
    cart_item = get_object_or_404(CartItem, uid=cart_item_uid)
    cart = cart_item.cart

    if not _can_access_cart(request, cart):
        return JsonResponse({'success': False, 'message': 'Forbidden'}, status=403)

    if action == 'increase':
        cart_item.quantity += 1
    elif action == 'decrease':
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
        else:
            cart_item.delete()
            total = sum(item.subtotal() for item in cart.cartitem_set.all())
            return JsonResponse({'success': True, 'deleted': True, 'total': total})
    else:
        return JsonResponse({'success': False, 'message': 'Invalid action.'}, status=400)

    cart_item.save()
    total = sum(item.subtotal() for item in cart.cartitem_set.all())
    return JsonResponse(
        {
            'success': True,
            'quantity': cart_item.quantity,
            'subtotal': cart_item.subtotal(),
            'total': total,
        }
    )


def initiate_payment(request):
    cart = _get_active_cart(request, create=True)
    cart_items = cart.cartitem_set.all()
    total = sum(item.subtotal() for item in cart_items)

    if request.method == 'POST':
        if total <= 0:
            return JsonResponse({'success': False, 'message': 'Your cart is empty.'}, status=400)

        payment_payload = {
            'amount': total,
            'email': request.POST.get('email'),
            'cart': cart,
            'full_name': request.POST.get('full_name'),
            'address': request.POST.get('address'),
            'city': request.POST.get('city'),
            'state': request.POST.get('state'),
            'phone_number': request.POST.get('phone_number'),
        }

        if request.user.is_authenticated:
            payment_payload['user'] = request.user
        else:
            payment_payload['session_id'] = _ensure_session(request)

        payment = Payment.objects.create(**payment_payload)
        context = {
            'payment': payment,
            'field_values': request.POST,
            'paystack_pub_key': settings.PAYSTACK_PUBLIC_KEY,
            'amount_value': payment.amount_value(),
        }
        return render(request, 'make_payment.html', context)

    return render(request, 'payment.html', {'cart': cart, 'total': total})


def sm(request):
    return redirect('/')


def viewpayment(request, ref):
    payment = get_object_or_404(Payment, ref=ref)
    if not _can_access_payment(request, payment):
        return HttpResponseForbidden('You are not allowed to view this payment.')

    cart = payment.cart
    cart_items = cart.cartitem_set.all()
    total = sum(item.subtotal() for item in cart_items)
    order = Order.objects.filter(payment=payment).first()
    return render(
        request,
        'success.html',
        {'cart_items': cart_items, 'total': total, 'cart': cart, 'payment': payment, 'order': order},
    )


def verify_payment(request, ref):
    payment = get_object_or_404(Payment, ref=ref)
    if not _can_access_payment(request, payment):
        return HttpResponseForbidden('You are not allowed to verify this payment.')

    cart = payment.cart
    cart_items = cart.cartitem_set.all()
    total = sum(item.subtotal() for item in cart_items)
    verified = payment.amount == total and payment.verify_payment()

    if verified:
        cart.cleared = True
        cart.save()
        order, _ = Order.objects.get_or_create(payment=payment)
        sender = settings.DEFAULT_FROM_EMAIL

        buyer_message = render_to_string(
            'order_confirmation_email.html',
            {'cart_items': cart_items, 'total': total, 'cart': cart, 'payment': payment, 'order': order},
        )
        send_mail(
            'Order Confirmation',
            strip_tags(buyer_message),
            sender,
            [payment.email],
            html_message=buyer_message,
        )

        seller_message = render_to_string(
            'new_order_email.html',
            {'cart_items': cart_items, 'total': total, 'cart': cart, 'payment': payment, 'order': order},
        )
        send_mail(
            'New Order Received',
            strip_tags(seller_message),
            sender,
            [sender],
            html_message=seller_message,
        )

        return render(
            request,
            'success.html',
            {'cart_items': cart_items, 'total': total, 'cart': cart, 'payment': payment, 'order': order},
        )

    return render(request, 'success.html', {'cart_items': cart_items, 'total': total, 'cart': cart, 'payment': payment})


@login_required
def payment_history(request):
    if request.user.is_staff:
        payment = Payment.objects.filter(verified=True)
    else:
        payment = Payment.objects.filter(verified=True, user=request.user)
    return render(request, 'payment_history.html', {'payments': payment})


@login_required
def sent_order(request, ref):
    if not request.user.is_staff:
        return HttpResponseForbidden('Only staff can update delivery status.')

    payment = get_object_or_404(Payment, ref=ref)
    order, _ = Order.objects.get_or_create(payment=payment)
    order.sent = True
    order.save(update_fields=['sent'])

    cart_items = payment.cart.cartitem_set.all()
    total = sum(item.subtotal() for item in cart_items)
    cart = payment.cart
    return render(request, 'success.html', {'cart_items': cart_items, 'total': total, 'cart': cart, 'payment': payment, 'order': order})


@login_required
def order_delivered(request, ref):
    if not request.user.is_staff:
        return HttpResponseForbidden('Only staff can update delivery status.')

    payment = get_object_or_404(Payment, ref=ref)
    order, _ = Order.objects.get_or_create(payment=payment)
    order.delivered = True
    order.save(update_fields=['delivered'])

    cart_items = payment.cart.cartitem_set.all()
    total = sum(item.subtotal() for item in cart_items)
    cart = payment.cart
    return render(request, 'success.html', {'cart_items': cart_items, 'total': total, 'cart': cart, 'payment': payment, 'order': order})
