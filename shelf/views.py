from django.shortcuts import get_object_or_404, redirect, render
from .models import Product, Category
from django.http import JsonResponse
from django.db.models import Q
from django.core.mail import send_mail
from django.core.cache import cache
from django.conf import settings
from .signals import HOMEPAGE_CACHE_KEY


def _shop_products():
    """Public products sold directly, excluding quote-only design bases."""
    return Product.objects.filter(is_public=True, customizable=False)


def homepage(request):
    products = cache.get(HOMEPAGE_CACHE_KEY)
    categories = Category.objects.all()
    images = ["home/img/6.png", "home/img/3.png", "home/img/2.png"]
    if not products:
        # Every field the product card reads must be listed, or each card
        # triggers extra queries for the deferred fields.
        products = _shop_products().only(
            'id', 'uid', 'name', 'price', 'image', 'stock', 'delivery', 'productType', 'minBuy', 'customizable', 'created_date'
        ).order_by('-created_date')[:24]
        products = list(products)
        cache.set(HOMEPAGE_CACHE_KEY, products, 300)  # Cache for 5 minutes
    return render(request, 'home/index.html', {'products': products, 'images':images, 'categories':categories})

def merchs(request):
    products = _shop_products().order_by('-created_date')
    categories = Category.objects.all()
    return render(request, 'home/merchs.html', {'products':products, 'categories':categories})

def FAQ(request):
    return render(request, 'home/faq.html')

def about(request):
    return render(request, 'home/about.html')

def returnPolicy(request):
    return render(request, 'home/returnPolicy.html')

def TermsCondition(request):
    return render(request, 'home/TermsCondition.html')


def privacyPolicy(request):
    return render(request, 'home/PrivacyPolicy.html')

def deliveryPolicy(request):
    return render(request, 'home/delivery.html')


def contact(request):
    context = {}
    if request.method == 'POST':
        name = request.POST.get('name', '')
        email = request.POST.get('email', '')
        message = request.POST.get('message', '')

        subject = 'Message from LOT Store Contact Form'
        body = f"Name: {name}\nEmail: {email}\nMessage: {message}"

        recipient_email = settings.DEFAULT_FROM_EMAIL or 'store@layersoftruth.org'

        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient_email], fail_silently=False)
            context['success_message'] = 'Message sent successfully. Our team will respond shortly.'
        except Exception:
            context['error_message'] = 'Unable to send message right now. Please try again later or use WhatsApp support.'

    return render(request, 'home/contact.html', context)

def category_view(request, cat):
    cate = get_object_or_404(Category, name=cat)
    products = _shop_products().filter(categories=cate).order_by('-created_date')
    info = f'Result for {cate.name} items'
    return render(request, 'home/merchs.html', {'products':products, 'info':info})


def details(request, uid):
    product = get_object_or_404(Product, uid=uid, is_public=True)
    products = _shop_products().filter(categories__in=product.categories.all()).exclude(uid=uid).distinct().order_by('-created_date')
    return render(request, 'home/details.html', {'product':product,'products':products})


def _to_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def filter_items(request):
    if request.method == 'POST':
        category_id = request.POST.get('category-filter')
        size_filter = request.POST.getlist('size')
        min_price_filter = request.POST.get('min-price')
        max_price_filter = request.POST.get('max-price')

        queryset = _shop_products().order_by('-created_date')

        category_pk = _to_int(category_id)
        if category_pk:
            queryset = queryset.filter(categories__id=category_pk)

        size_ids = [pk for pk in (_to_int(size) for size in size_filter) if pk]
        if size_ids:
            queryset = queryset.filter(size__id__in=size_ids)

        min_price = _to_int(min_price_filter)
        if min_price is not None:
            queryset = queryset.filter(price__gte=min_price)

        max_price = _to_int(max_price_filter)
        if max_price is not None:
            queryset = queryset.filter(price__lte=max_price)

        queryset = queryset.distinct()
        info = f"Filter result: {len(queryset)}"
        context ={
                'products': queryset, 
                'info':info,
                'category_id':category_id,
                'size_filter':size_filter,
                'min_price_filter':min_price_filter,
                'max_price_filter':max_price_filter,
            }
        return render(request, 'home/index.html', context)

    return redirect('homepage')


from .models import SearchQuery

def search(request):
    search = (request.GET.get('item') or '').strip()
    if search:
        filtered_items = _shop_products().filter(
            Q(name__icontains=search) | 
            Q(categories__name__icontains=search) | 
            Q(size__name__icontains=search) | 
            Q(description__icontains=search)
        ).distinct()
        info = f"Search result for {search}: {len(filtered_items)}"
        user = request.user if request.user.is_authenticated else None
        ip_address = request.META.get('REMOTE_ADDR')

        SearchQuery.objects.create(user=user, query=search[:255], ip_address=ip_address)
    else:
        filtered_items = _shop_products().order_by('-created_date')
        info = "Enter a product name, size or category to search"
    return render(request, 'home/index.html', {'products':filtered_items, 'info':info}) 

def search_suggestions(request):
    search_term = (request.GET.get('item') or '').strip()
    if search_term:
        suggestions = _shop_products().filter(name__icontains=search_term).prefetch_related('size')[:5]
        suggestions_data = []
        for product in suggestions:
            product_data = {
                'name': product.name,
                'size': ', '.join(s.name for s in product.size.all()),
                'price': product.price,
                'image': product.image.url if product.image else '',
                'details_url': product.uid # Assuming you have a method to get product details URL
            }
            suggestions_data.append(product_data)
        return JsonResponse({'suggestions': suggestions_data})
    return JsonResponse({'suggestions': []})
