from django.shortcuts import get_object_or_404, render
from .models import Product, Category
from django.http import JsonResponse
from django.db.models import Q
from django.core.mail import send_mail
from django.core.cache import cache
from django.conf import settings

def homepage(request):
    products = cache.get('homepage_products')
    categories = Category.objects.all()
    images = ["home/img/6.png", "home/img/3.png", "home/img/2.png"]
    if not products:
        products = Product.objects.all().only(
            'id', 'name', 'price', 'image', 'created_date'
        ).order_by('-created_date')[:24]
        cache.set('homepage_products', products, 300)  # Cache for 5 minutes
    return render(request, 'home/index.html', {'products': products, 'images':images, 'categories':categories})

def merchs(request):
    products = Product.objects.all().order_by('-created_date')
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
    products = Product.objects.filter(categories=cate).order_by('-created_date')
    info = f'Result for {cate.name} items'
    return render(request, 'home/merchs.html', {'products':products, 'info':info})


def details(request, uid):
    product = get_object_or_404(Product, uid=uid)
    products = Product.objects.filter(categories__in=product.categories.all()).exclude(uid=uid).distinct().order_by('-created_date')
    return render(request, 'home/details.html', {'product':product,'products':products})


def filter_items(request):
    if request.method == 'POST':
        category_id = request.POST.get('category-filter')
        size_filter = request.POST.getlist('size')
        min_price_filter = request.POST.get('min-price')
        max_price_filter = request.POST.get('max-price')

        queryset = Product.objects.all()

        if category_id != '0':
            queryset = queryset.filter(categories__id=category_id)

        if size_filter:
            size_q_objects = Q()
            for size in size_filter:
                size_q_objects |= Q(size=size)
            queryset = queryset.filter(size_q_objects)

        if min_price_filter:
            queryset = queryset.filter(price__gte=min_price_filter)
        else:
            queryset = queryset.filter(price__gte=0)

        if max_price_filter:
            queryset = queryset.filter(price__lte=max_price_filter)
        else:
            queryset = queryset.filter(price__lte=10000)

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

    return render(request, 'home/index.html')  


from .models import SearchQuery

def search(request):
    search = request.GET.get('item')
    if search:
        filtered_items = Product.objects.filter(
            Q(name__icontains=search) | 
            Q(categories__name__icontains=search) | 
            Q(size__name__icontains=search) | 
            Q(description__icontains=search)
        ).distinct()
        info = f"Search result for {search}: {len(filtered_items)}"
        user = request.user if request.user.is_authenticated else None
        ip_address = request.META.get('REMOTE_ADDR')

        if search:
            SearchQuery.objects.create(user=user, query=search, ip_address=ip_address)
    else:
        filtered_items =  Product.objects.all()
        info = f"Search result for {search} not found"
    return render(request, 'home/index.html', {'products':filtered_items, 'info':info}) 

def search_suggestions(request):
    if 'item' in request.GET:
        search_term = request.GET['item']
        suggestions = Product.objects.filter(name__icontains=search_term)[:5]
        suggestions_data = []
        for product in suggestions:
            product_data = {
                'name': product.name,
                'size': ', '.join(product.size.values_list('name', flat=True)),
                'price': product.price,
                'image': product.image.url,  # Assuming image field is a FileField or ImageField
                'details_url': product.uid # Assuming you have a method to get product details URL
            }
            suggestions_data.append(product_data)
        return JsonResponse({'suggestions': suggestions_data})
    return JsonResponse({})
