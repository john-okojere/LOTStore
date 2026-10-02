import json
import logging

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.models import LogEntry
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import IntegrityError
from django.db.models import Count
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from requests import RequestException

from cart.models import Cart, CartActivity, CartItem, Order, Payment
from shelf.models import Category, Product, ProductView, SearchQuery, Sizes
from user.models import Staff, User

from .forms import ProductForm

logger = logging.getLogger(__name__)


def _is_dashboard_admin(user):
    return user.is_authenticated and (user.is_staff or getattr(user, "level", 0) >= 2)


def _forbidden_json():
    return JsonResponse({"error": "Unauthorized"}, status=403)


def _forbidden_page():
    return HttpResponseForbidden("Unauthorized")


@login_required
def admin_dashboard(request):
    if not _is_dashboard_admin(request.user):
        return redirect("/")

    product_views = ProductView.objects.select_related("product", "user").order_by("-timestamp")[:300]
    cart_activities = CartActivity.objects.select_related("product", "user").order_by("-timestamp")[:300]

    most_viewed_products = Product.objects.annotate(
        view_count=Count("views", distinct=True)
    ).order_by("-view_count")[:5]

    most_added_products = Product.objects.annotate(
        cart_count=Count("cartactivity__id", distinct=True)
    ).order_by("-cart_count")[:5]

    state_distribution = (
        ProductView.objects.exclude(state__isnull=True)
        .exclude(state="")
        .values("state")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )
    country_distribution = (
        ProductView.objects.exclude(country__isnull=True)
        .exclude(country="")
        .values("country")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    top_visitors = (
        ProductView.objects.values("user__first_name", "user__last_name", "ip_address")
        .annotate(total_views=Count("id"), unique_products=Count("product", distinct=True))
        .order_by("-total_views")[:10]
    )

    recent_admin_logs = LogEntry.objects.select_related("user", "content_type").order_by("-action_time")[:20]

    context = {
        "product_views": product_views,
        "cart_activities": cart_activities,
        "most_viewed_products": most_viewed_products,
        "most_added_products": most_added_products,
        "state_distribution": state_distribution,
        "country_distribution": country_distribution,
        "top_visitors": top_visitors,
        "recent_admin_logs": recent_admin_logs,
    }
    return render(request, "dashboard/home.html", context)


@login_required
def system_logs(request):
    if not _is_dashboard_admin(request.user):
        return redirect("/")

    admin_logs = LogEntry.objects.select_related("user", "content_type").order_by("-action_time")[:200]
    recent_searches = SearchQuery.objects.select_related("user").order_by("-timestamp")[:200]
    recent_views = ProductView.objects.select_related("user", "product").order_by("-timestamp")[:200]
    recent_cart_adds = CartActivity.objects.select_related("user", "product").order_by("-timestamp")[:200]

    context = {
        "admin_logs": admin_logs,
        "recent_searches": recent_searches,
        "recent_views": recent_views,
        "recent_cart_adds": recent_cart_adds,
    }
    return render(request, "dashboard/system_logs.html", context)


# users ==================================================================================================================================
@login_required
def all_users(request):
    if not _is_dashboard_admin(request.user):
        return redirect(".")
    return render(request, "dashboard/users/all_user.html", {})


@login_required
def all_staffs(request):
    if not _is_dashboard_admin(request.user):
        return redirect(".")
    return render(request, "dashboard/users/all_staff.html", {})


@login_required
def delete_user(request, user_id):
    if not _is_dashboard_admin(request.user):
        return _forbidden_json()

    if request.method not in ("POST", "DELETE"):
        return JsonResponse({"error": "Method not allowed"}, status=405)

    user = get_object_or_404(User, id=user_id)
    if user.is_superuser or user == request.user:
        return JsonResponse({"error": "This account cannot be deleted here."}, status=403)
    user.delete()
    return JsonResponse({"status": "success"})


@login_required
def edit_user(request, user_id):
    if not _is_dashboard_admin(request.user):
        return _forbidden_json()

    user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid data"}, status=400)

        email = (data.get("email") or user.email).strip().lower()
        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse({"error": "Enter a valid email address."}, status=400)
        if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            return JsonResponse({"error": "That email is already used by another account."}, status=400)

        gender = data.get("gender", user.gender)
        if gender not in ("Male", "Female", None, ""):
            return JsonResponse({"error": "Invalid gender."}, status=400)

        user.first_name = data.get("first_name", user.first_name)
        user.last_name = data.get("last_name", user.last_name)
        user.email = email
        user.gender = gender or None
        user.save()
        return JsonResponse({"status": "success"})

    user_data = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "gender": user.gender,
    }
    return JsonResponse(user_data)


@login_required
def view_user(request, user_id):
    if not _is_dashboard_admin(request.user):
        return redirect("/")

    user = get_object_or_404(User, id=user_id)
    carts = Cart.objects.filter(user=user)
    cart_items = CartItem.objects.filter(cart__in=carts).select_related("product").prefetch_related("size")
    payments = Payment.objects.filter(user=user)
    orders = Order.objects.filter(payment__in=payments)

    context = {
        "person": user,
        "carts": carts,
        "cart_items": cart_items,
        "payments": payments,
        "orders": orders,
    }
    return render(request, "dashboard/users/view_user.html", context)


@login_required
def view_staff(request, staff_id):
    if not _is_dashboard_admin(request.user):
        return redirect("/")

    staff = get_object_or_404(Staff, id=staff_id)
    return render(request, "dashboard/users/view_staff.html", {"staff": staff})


@login_required
def get_user_orders(request, user_id):
    if not _is_dashboard_admin(request.user):
        return _forbidden_json()

    orders = Order.objects.filter(payment__user_id=user_id).values(
        "payment__amount", "payment__verified", "packed", "sent", "delivered", "date_created"
    )
    return JsonResponse({"data": list(orders)})


@login_required
def get_user_cart(request, user_id):
    if not _is_dashboard_admin(request.user):
        return _forbidden_json()

    cart_items = CartItem.objects.filter(cart__user_id=user_id).select_related("product").prefetch_related("size")
    data = [
        {
            "product__name": item.product.name,
            "quantity": item.quantity,
            "size": ", ".join(item.size.values_list("name", flat=True)),
            "created_date": item.created_date,
        }
        for item in cart_items
    ]
    return JsonResponse({"data": data})


@login_required
def get_user_payments(request, user_id):
    if not _is_dashboard_admin(request.user):
        return _forbidden_json()

    payments = Payment.objects.filter(user_id=user_id).values("amount", "verified", "date_created")
    return JsonResponse({"payments": list(payments)})


# APIs ==================================================================================================================================
@login_required
def api_all_users(request):
    if not _is_dashboard_admin(request.user):
        return _forbidden_json()

    all_users = []
    all_user = User.objects.all().exclude(is_staff=True)
    for user in all_user:
        cart, _ = Cart.objects.get_or_create(user=user, cleared=False)
        all_users.append(
            {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "gender": user.gender,
                "cart_item_count": cart.cartitem_set.count(),
            }
        )
    return JsonResponse({"data": all_users}, safe=False)


@login_required
def api_all_staff(request):
    if not _is_dashboard_admin(request.user):
        return _forbidden_json()

    all_users = []
    all_user = Staff.objects.select_related("user").all().exclude(user__is_staff=True)
    for user in all_user:
        all_users.append(
            {
                "id": user.id,
                "user": {
                    "first_name": user.user.first_name,
                    "last_name": user.user.last_name,
                    "email": user.user.email,
                    "gender": user.user.gender,
                },
                "level": user.level,
                "role": user.role,
                "country": user.country,
                "state": user.state,
                "date_joined": user.date_joined,
            }
        )
    return JsonResponse({"data": all_users}, safe=False)


# Order =========================================================================
@login_required
def manage_orders(request):
    if not _is_dashboard_admin(request.user):
        return _forbidden_page()

    orders = Order.objects.select_related("payment").order_by("-date_created")
    status_filter = request.GET.get("status") or "all"

    if status_filter == "pending":
        orders = orders.filter(packed=False, sent=False, delivered=False)
    elif status_filter == "packed":
        orders = orders.filter(packed=True, sent=False, delivered=False)
    elif status_filter == "sent":
        orders = orders.filter(sent=True, delivered=False)
    elif status_filter == "delivered":
        orders = orders.filter(delivered=True)

    return render(request, "dashboard/orders/manage_orders.html", {"filter": status_filter, "orders": orders})


@login_required
def update_order_status(request, order_id, status):
    if not _is_dashboard_admin(request.user):
        return _forbidden_page()

    if request.method != "POST":
        return redirect("manage_orders")

    order = get_object_or_404(Order.objects.select_related("payment"), id=order_id)
    if status == "packed":
        order.packed = True
    elif status == "sent":
        order.packed = order.sent = True
    elif status == "delivered":
        order.packed = order.sent = order.delivered = True
    else:
        messages.error(request, "Unknown order status.")
        return redirect("order_detail", order_id=order.id)
    order.save()

    if status in ("sent", "delivered"):
        _notify_customer_of_status(request, order, status)
    messages.success(request, f"Order #{order.id} marked as {status}.")
    return redirect("order_detail", order_id=order.id)


def _notify_customer_of_status(request, order, status):
    payment = order.payment
    if not payment.email:
        return
    link = request.build_absolute_uri(reverse("payment_view", args=[payment.ref]))
    if status == "sent":
        subject = "Your LOT Store order is on its way"
        body = "Good news! Your order has been sent out for delivery."
    else:
        subject = "Your LOT Store order has been delivered"
        body = "Your order has been marked as delivered. We hope you enjoy it!"
    message = (
        f"Hello {payment.full_name or ''},\n\n{body}\n\n"
        f"Order reference: {payment.ref}\nView your order: {link}\n\n"
        "Thank you for shopping with LOT Store."
    )
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [payment.email])
    except Exception:
        logger.exception("Failed to send order status email for order %s", order.id)


@login_required
def order_detail(request, order_id):
    if not _is_dashboard_admin(request.user):
        return _forbidden_page()

    order = get_object_or_404(Order, id=order_id)
    payment = order.payment
    cart_items = order.payment.cart.cartitem_set.all()

    context = {
        "order": order,
        "payment": payment,
        "cart_items": cart_items,
    }
    return render(request, "dashboard/orders/order_detail.html", context)


# Product =========================================================================
def _save_named(request, obj):
    name = (request.POST.get("name") or "").strip()
    if not name:
        return JsonResponse({"success": False, "error": "Name is required."}, status=400)
    if type(obj).objects.filter(name__iexact=name).exclude(pk=obj.pk).exists():
        return JsonResponse({"success": False, "error": f'"{name}" already exists.'}, status=400)
    obj.name = name
    try:
        obj.save()
    except IntegrityError:
        return JsonResponse({"success": False, "error": f'"{name}" already exists.'}, status=400)
    return JsonResponse({"success": True})


@login_required
def product_category(request):
    if not _is_dashboard_admin(request.user):
        return _forbidden_page()
    product_category_items = Category.objects.all()
    return render(request, "dashboard/product/category.html", {"category": product_category_items})


@login_required
def add_category(request):
    if not _is_dashboard_admin(request.user):
        return _forbidden_json()

    if request.method == "POST":
        return _save_named(request, Category())
    return JsonResponse({"success": False, "error": "Invalid request"}, status=405)


@login_required
def update_category(request, category_id):
    if not _is_dashboard_admin(request.user):
        return _forbidden_json()

    if request.method == "POST":
        category = get_object_or_404(Category, id=category_id)
        return _save_named(request, category)
    return JsonResponse({"success": False})


@login_required
def delete_category(request, category_id):
    if not _is_dashboard_admin(request.user):
        return _forbidden_json()

    if request.method == "POST":
        category = get_object_or_404(Category, id=category_id)
        category.delete()
        return JsonResponse({"success": True})
    return JsonResponse({"success": False})


@login_required
def product_sizes(request):
    if not _is_dashboard_admin(request.user):
        return _forbidden_page()

    product_sizes_items = Sizes.objects.all()
    return render(request, "dashboard/product/sizes.html", {"sizes": product_sizes_items})


@login_required
def add_sizes(request):
    if not _is_dashboard_admin(request.user):
        return _forbidden_json()

    if request.method == "POST":
        return _save_named(request, Sizes())
    return JsonResponse({"success": False, "error": "Invalid request"}, status=405)


@login_required
def update_sizes(request, sizes_id):
    if not _is_dashboard_admin(request.user):
        return _forbidden_json()

    if request.method == "POST":
        sizes = get_object_or_404(Sizes, id=sizes_id)
        return _save_named(request, sizes)
    return JsonResponse({"success": False})


@login_required
def delete_sizes(request, sizes_id):
    if not _is_dashboard_admin(request.user):
        return _forbidden_json()

    if request.method == "POST":
        sizes = get_object_or_404(Sizes, id=sizes_id)
        sizes.delete()
        return JsonResponse({"success": True})
    return JsonResponse({"success": False})


@login_required
def product_list_api(request):
    if not _is_dashboard_admin(request.user):
        return _forbidden_json()

    products = Product.objects.prefetch_related("categories").all()
    data = []
    for product in products:
        data.append(
            {
                "uid": product.uid,
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "stock": product.stock,
                "productType": product.productType,
                "categories": ", ".join(cat.name for cat in product.categories.all()),
                "image": product.image.url if product.image else "/static/images/default.png",
            }
        )
    return JsonResponse({"data": data})


@login_required
def product_list_view(request):
    if not _is_dashboard_admin(request.user):
        return _forbidden_page()
    return render(request, "dashboard/product/all.html")


@login_required
def delete_product(request, uid):
    if not _is_dashboard_admin(request.user):
        return _forbidden_json()

    if request.method not in ("POST", "DELETE"):
        return JsonResponse({"error": "Method not allowed"}, status=405)

    product = get_object_or_404(Product, uid=uid)
    product.delete()
    if request.method == "POST":
        return redirect("product_list")
    return JsonResponse({"message": "Product deleted successfully"})


@login_required
def add_product(request):
    if not _is_dashboard_admin(request.user):
        return _forbidden_page()

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.user = request.user
            product.save()
            form.save_m2m()
            messages.success(request, f"Product \"{product.name}\" added.")
            return redirect("product_list")
    else:
        form = ProductForm()

    return render(request, "dashboard/product/add_product.html", {"form": form})


@login_required
def edit_product(request, uid):
    if not _is_dashboard_admin(request.user):
        return _forbidden_page()

    product = get_object_or_404(Product, uid=uid)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product_obj = form.save(commit=False)
            product_obj.save()
            form.save_m2m()
            messages.success(request, f"Product \"{product_obj.name}\" updated.")
            return redirect("product_list")
    else:
        form = ProductForm(instance=product)

    return render(request, "dashboard/product/add_product.html", {"form": form})


@login_required
def product_detail_view(request, uid):
    if not _is_dashboard_admin(request.user):
        return _forbidden_page()

    product = get_object_or_404(Product, uid=uid)
    product_views = ProductView.objects.filter(product=product).select_related("user").order_by("-timestamp")
    cart_activities = CartActivity.objects.filter(product=product).select_related("user").order_by("-timestamp")

    context = {
        "product": product,
        "product_views": product_views,
        "cart_activities": cart_activities,
        "total_views": product_views.count(),
        "total_cart_adds": cart_activities.count(),
    }
    return render(request, "dashboard/product/detail.html", context)


# Traffic =========================================================================
def get_location(ip_address):
    if not ip_address:
        return {"city": None, "region": None, "country": None}

    try:
        response = requests.get(f"https://ipinfo.io/{ip_address}/json", timeout=3)
        data = response.json()
        return {
            "city": data.get("city"),
            "region": data.get("region"),
            "country": data.get("country"),
        }
    except (RequestException, ValueError):
        return {"city": None, "region": None, "country": None}


@csrf_exempt
def track_time_spent(request):
    if request.method != "POST":
        return JsonResponse({"status": "error"}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid payload"}, status=400)

    product_uid = data.get("product_uid")
    try:
        time_spent = int(data.get("time_spent") or 0)
    except (TypeError, ValueError):
        time_spent = 0

    product = get_object_or_404(Product, uid=product_uid)
    user = request.user if request.user.is_authenticated else None
    ip_address = request.META.get("REMOTE_ADDR")

    location = get_location(ip_address)
    region = location.get("region")
    country = location.get("country")

    ProductView.objects.create(
        user=user,
        product=product,
        ip_address=ip_address,
        duration=max(time_spent, 0),
        state=region,
        country=country,
    )

    return JsonResponse({"status": "success", "state": region, "country": country})


@csrf_exempt
def track_add_to_cart(request):
    if request.method != "POST":
        return JsonResponse({"status": "error"}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid payload"}, status=400)

    product_uid = data.get("product_uid")

    product = get_object_or_404(Product, uid=product_uid)
    user = request.user if request.user.is_authenticated else None
    ip_address = request.META.get("REMOTE_ADDR")

    location = get_location(ip_address)
    region = location.get("region")
    country = location.get("country")

    CartActivity.objects.create(
        user=user,
        product=product,
        ip_address=ip_address,
        state=region,
        country=country,
    )

    return JsonResponse({"status": "success", "state": region, "country": country})
