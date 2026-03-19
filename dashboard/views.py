import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from user.models import User, Staff
from cart.models import Cart, CartItem
from shelf.models import Product
from django.http import HttpResponseForbidden, JsonResponse
from django.db.models import Count

@login_required
def admin_dashboard(request):
    if request.user.level >= 2:
       # Fetch data for product views and cart activities
        product_views = ProductView.objects.all().order_by('-timestamp')
        cart_activities = CartActivity.objects.all().order_by('-timestamp')

        # Most viewed products
        most_viewed_products = Product.objects.annotate(view_count=Count('views')).order_by('-view_count')[:5]

        # Most added to cart products
        most_added_products = Product.objects.annotate(cart_count=Count('cartactivity')).order_by('-cart_count')[:5]

        # User locations (state & country distribution)
        state_distribution = ProductView.objects.values('state').annotate(count=Count('id'))
        country_distribution = ProductView.objects.values('country').annotate(count=Count('id'))

        context = {
            'product_views': product_views,
            'cart_activities': cart_activities,
            'most_viewed_products': most_viewed_products,
            'most_added_products': most_added_products,
            'state_distribution': state_distribution,
            'country_distribution': country_distribution,
        }
        return render(request, 'dashboard/home.html', context)
    else:
        return redirect('/')
    
#users ==================================================================================================================================
@login_required
def all_users(request):
    if request.user.level >= 2:
        context = {
        }
        return render(request, 'dashboard/users/all_user.html', context)
    else:
        return redirect('.')

@login_required
def all_staffs(request):
    if request.user.level >= 2:
        context = {
        }
        return render(request, 'dashboard/users/all_staff.html', context)
    else:
        return redirect('.')    

@login_required
def delete_user(request, user_id):
    if request.user.level >= 2:
        user = User.objects.get(id=user_id)
        user.delete()
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'error': 'Unauthorized'}, status=403)


@login_required
def edit_user(request, user_id):
    if request.user.level >= 2:
        user = User.objects.get(id=user_id)
        if request.method == 'POST':
            data = json.loads(request.body)
            user.first_name = data.get('first_name', user.first_name)
            user.last_name = data.get('last_name', user.last_name)
            user.email = data.get('email', user.email)
            user.gender = data.get('gender', user.gender)
            user.save()
            return JsonResponse({'status': 'success'})
        else:
            user_data = {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'gender': user.gender,
            }
            return JsonResponse(user_data)
    else:
        return JsonResponse({'error': 'Unauthorized'}, status=403)


@login_required
def view_user(request, user_id):
    if request.user.level >= 2:
        user = get_object_or_404(User, id=user_id)

        # Get User's Cart
        carts = Cart.objects.filter(user=user)
        cart_items = CartItem.objects.filter(cart__in=carts)

        # Get User's Orders
        payments = Payment.objects.filter(user=user)
        orders = Order.objects.filter(payment__in=payments)

        context = {
            "person": user,
            "carts": carts,
            "cart_items": cart_items,
            "payments": payments,
            "orders": orders,
        }
        return render(request, 'dashboard/users/view_user.html', context)
    else:
        return redirect('/')

@login_required
def view_staff(request, staff_id):
    if request.user.level >= 2:
        staff = get_object_or_404(Staff, id=staff_id)
        context = {
            "staff": staff,
        }
        return render(request, 'dashboard/users/view_staff.html', context)
    else:
        return redirect('/')


# def view 

@login_required
def get_user_orders(request, user_id):
    if request.user.level < 2:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    orders = Order.objects.filter(payment__user_id=user_id).values(
        "payment__amount", "payment__verified", "packed" ,"sent", "delivered", "date_created"
    )
    return JsonResponse({"data": list(orders)})

@login_required
def get_user_cart(request, user_id):
    if request.user.level < 2:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    cart_items = CartItem.objects.filter(cart__user_id=user_id).values(
        "product__name", "quantity", 'size' ,"created_date"
    )
    return JsonResponse({"data": list(cart_items)})

@login_required
def get_user_payments(request, user_id):
    if request.user.level < 2:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    payments = Payment.objects.filter(user_id=user_id).values(
        "amount", "verified", "date_created"
    )
    return JsonResponse({"payments": list(payments)})
# APIs ==================================================================================================================================

@login_required
def api_all_users(request):
    if request.user.level >= 2:
        all_users = []
        all_user = User.objects.all().exclude(is_staff=True)
        for user in all_user:
            cart, created = Cart.objects.get_or_create(user=user, cleared= False)
            user.cart_item_count = cart.cartitem_set.count()
            all_users.append({
                'id': user.id,
                'first_name':user.first_name,
                'last_name':user.last_name,
                'email':user.email,
                'gender':user.gender,
                'cart_item_count':user.cart_item_count,
            })
        return JsonResponse({'data' : all_users}, safe=False)
    else:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

@login_required
def api_all_staff(request):
    if request.user.level >= 2:
        all_users = []
        all_user = Staff.objects.all().exclude(user__is_staff=True)
        for user in all_user:
            all_users.append({
                'id': user.id,
                'user': {
                    'first_name': user.user.first_name,
                    'last_name': user.user.last_name,
                    'email': user.user.email,
                    'gender': user.user.gender,
                },
                'level':user.level,
                'role':user.role,
                'country': user.country,
                'state':user.state,
                'date_joined':user.date_joined
            })
        return JsonResponse({'data' : all_users}, safe=False)
    else:
        return JsonResponse({'error': 'Unauthorized'}, status=403)



# Order =========================================================================

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from cart.models import Order, Payment

@login_required
def manage_orders(request):
    if request.user.level < 2:
        return HttpResponseForbidden('Unauthorized')
    orders = Order.objects.select_related("payment").all()
    status_filter = request.GET.get("status")
    if status_filter:
        pass
    else:
        status_filter = "all"

    if status_filter == "packed":
        orders = orders.filter(packed =False, sent=False, delivered=False)
    elif status_filter == "pending":
        orders = orders.filter(sent=False, delivered=False)
    elif status_filter == "sent":
        orders = orders.filter(sent=True, delivered=False)
    elif status_filter == "delivered":
        orders = orders.filter(delivered=True)
    
    return render(request, "dashboard/orders/manage_orders.html", {"filter":status_filter,"orders": orders})


@login_required
def update_order_status(request, order_id, status):
    if request.user.level < 2:
        return HttpResponseForbidden('Unauthorized')
    order = get_object_or_404(Order, id=order_id)

    if status == "packed":
        order.packed = True
    elif status == "sent":
        order.sent = True
    elif status == "delivered":
        order.delivered = True

    order.save()
    return redirect("manage_orders")

@login_required
def order_detail(request, order_id):
    if request.user.level < 2:
        return HttpResponseForbidden('Unauthorized')
    # Get the order with related payment details
    order = get_object_or_404(Order, id=order_id)
    payment = order.payment  # Associated payment
    cart_items = order.payment.cart.cartitem_set.all()  # Products in the order

    context = {
        'order': order,
        'payment': payment,
        'cart_items': cart_items,
    }

    return render(request, 'dashboard/orders/order_detail.html', context)

# Product =========================================================================

from .forms import ProductForm
from shelf.models import Product, Category, Sizes

@login_required
def product_category(request):
    if request.user.level < 2:
        return HttpResponseForbidden('Unauthorized')
    product_category = Category.objects.all()
    return render(request, 'dashboard/product/category.html', {'category':product_category})

@login_required
def add_category(request):
    if request.user.level < 2:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    if request.method == "POST":
        name = request.POST.get("name")
        if name:
            Category.objects.create(name=name)
            return JsonResponse({"success": True})
    return JsonResponse({"success": False})

@login_required
def update_category(request, category_id):
    if request.user.level < 2:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    if request.method == "POST":
        category = get_object_or_404(Category, id=category_id)
        new_name = request.POST.get("name")
        category.name = new_name
        category.save()
        return JsonResponse({"success": True})
    return JsonResponse({"success": False})

@login_required
def delete_category(request, category_id):
    if request.user.level < 2:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    if request.method == "POST":
        category = get_object_or_404(Category, id=category_id)
        category.delete()
        return JsonResponse({"success": True})
    return JsonResponse({"success": False})


@login_required
def product_sizes(request):
    if request.user.level < 2:
        return HttpResponseForbidden('Unauthorized')
    product_sizes = Sizes.objects.all()
    return render(request, 'dashboard/product/sizes.html', {'sizes':product_sizes})

@login_required
def add_sizes(request):
    if request.user.level < 2:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    if request.method == "POST":
        name = request.POST.get("name")
        if name:
            Sizes.objects.create(name=name)
            return JsonResponse({"success": True})
    return JsonResponse({"success": False})

@login_required
def update_sizes(request, sizes_id):
    if request.user.level < 2:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    if request.method == "POST":
        sizes = get_object_or_404(Sizes, id=sizes_id)
        new_name = request.POST.get("name")
        sizes.name = new_name
        sizes.save()
        return JsonResponse({"success": True})
    return JsonResponse({"success": False})

@login_required
def delete_sizes(request, sizes_id):
    if request.user.level < 2:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    if request.method == "POST":
        sizes = get_object_or_404(Sizes, id=sizes_id)
        sizes.delete()
        return JsonResponse({"success": True})
    return JsonResponse({"success": False})


@login_required
def product_list_api(request):
    if request.user.level < 2:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    products = Product.objects.all().values('uid','id' ,'name', 'price', 'stock', 'productType', 'image')
    data = list(products)
    for product in data:
        product_obj = Product.objects.get(uid=product['uid'])
        product['categories'] = ', '.join([cat.name for cat in product_obj.categories.all()])
        product['image'] = product_obj.image.url if product_obj.image else '/static/images/default.png'
    return JsonResponse({"data": data})

@login_required
def product_list_view(request):
    if request.user.level < 2:
        return HttpResponseForbidden('Unauthorized')
    return render(request, 'dashboard/product/all.html')

@login_required
def delete_product(request, uid):
    if request.user.level < 2:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    product = get_object_or_404(Product, uid=uid)
    product.delete()
    return JsonResponse({"message": "Product deleted successfully"})

@login_required
def add_product(request):
    if request.user.level < 2:
        return HttpResponseForbidden('Unauthorized')
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.save(commit=False)
            f.user = request.user
            form.save()
            return redirect('/')
    else:
        form = ProductForm()
    
    return render(request, 'dashboard/product/add_product.html', {'form': form})

@login_required
def edit_product(request, uid):
    if request.user.level < 2:
        return HttpResponseForbidden('Unauthorized')
    product  = Product.objects.get(uid = uid)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            f = form.save(commit=False)
            f.user = request.user
            form.save()
            return redirect('product_list')
    else:
        form = ProductForm(instance=product)
    
    return render(request, 'dashboard/product/add_product.html', {'form': form})

@login_required
def product_detail_view(request, uid):
    if request.user.level < 2:
        return HttpResponseForbidden('Unauthorized')
    product = get_object_or_404(Product, uid=uid)
     # Get analytics data
    product_views = ProductView.objects.filter(product=product).order_by("-timestamp")
    cart_activities = CartActivity.objects.filter(product=product).order_by("-timestamp")

    context = {
        "product": product,
        "product_views": product_views,
        "cart_activities": cart_activities,
        "total_views": product_views.count(),
        "total_cart_adds": cart_activities.count(),
    }
    return render(request, 'dashboard/product/detail.html', context)


# Traffic =========================================================================
import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from shelf.models import Product, ProductView
from cart.models import CartActivity

# Function to get location from IP address
def get_location(ip_address):
    try:
        response = requests.get(f"https://ipinfo.io/{ip_address}/json")
        data = response.json()
        return {
            "city": data.get("city"),
            "region": data.get("region"),  # State
            "country": data.get("country"),
        }
    except:
        return {"city": None, "region": None, "country": None}

@csrf_exempt
def track_time_spent(request):
    if request.method == "POST":
        data = json.loads(request.body)
        product_uid = data.get("product_uid")
        time_spent = data.get("time_spent")

        product = Product.objects.get(uid=product_uid)
        user = request.user if request.user.is_authenticated else None
        ip_address = request.META.get('REMOTE_ADDR')

        # Get location details
        location = get_location(ip_address)
        region = location["region"]  # State
        country = location["country"]

        # Save product view
        ProductView.objects.create(
            user=user, product=product, ip_address=ip_address, duration=time_spent
        )

        return JsonResponse({"status": "success", "state": region, "country": country})
    return JsonResponse({"status": "error"}, status=400)

@csrf_exempt
def track_add_to_cart(request):
    if request.method == "POST":
        data = json.loads(request.body)
        product_uid = data.get("product_uid")

        product = Product.objects.get(uid=product_uid)
        user = request.user if request.user.is_authenticated else None
        ip_address = request.META.get('REMOTE_ADDR')

        # Get location details
        location = get_location(ip_address)
        region = location["region"]  # State
        country = location["country"]

        # Save cart activity
        CartActivity.objects.create(user=user, product=product, ip_address=ip_address)

        return JsonResponse({"status": "success", "state": region, "country": country})
    return JsonResponse({"status": "error"}, status=400)
