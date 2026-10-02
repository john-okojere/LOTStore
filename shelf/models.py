from django.db import models
import uuid
from user.models import User

class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_date = models.DateTimeField(auto_now=True, null=True)
    
    def __str__(self):
        return self.name

class Sizes(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_date = models.DateTimeField(auto_now=True, null=True)
    
    def __str__(self):
        return self.name

Size = (
    ('Baby Size', 'Baby Size'),
    ('Small', 'Small'),
    ('Medium', 'Medium'),
    ('Large', 'Large'),
    ('X-Large', 'X-Large'),
    ('XX-Large', 'XX-Large'),
    ('XXX-Large', 'XXX-Large')
)

pays = (
    ('Pay on Delivery', 'Pay on Delivery'),
    ('Pay before Delivery', 'Pay                                                                  before Delivery'),
)

delivery = (
    ('Free Delivery', 'Free Delivery'),
    ('Delivery Fee', 'Delivery Fee'),
)

productType = (
    ('Single Buy', 'Single Buy'),
    ('Min. Buy', 'Min. Buy'),
    ('Gift on Buy', 'Gift on Buy'),
)

class Product(models.Model):
    uid = models.UUIDField( default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to='product/%y/%m/%d/')
    categories = models.ManyToManyField(Category, related_name='product')
    size = models.ManyToManyField(Sizes)
    price = models.IntegerField()
    stock = models.IntegerField(verbose_name="number of Available Stock")
    description = models.TextField()
    pay = models.CharField(max_length=25, choices=pays , default='Pay before Delivery')
    delivery = models.CharField(choices=delivery, max_length=25, default='Delivery Fee')
    productType = models.CharField(choices=productType, max_length=25, default='Single Buy')
    minBuy = models.IntegerField(verbose_name="minBuy", default=1)
    customizable = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True, db_index=True)
    updated_date = models.DateTimeField(auto_now=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True, null=True)



    def __str__(self):
        return self.name
    

from django.db import models
from django.utils.timezone import now
import uuid


class ProductView(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='views')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(default=now)
    duration = models.IntegerField(default=0)  # Store duration in seconds
    state = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.user if self.user else 'Anonymous'} viewed {self.product.name} for {self.duration} sec"


class SearchQuery(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    query = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(default=now)
    state = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.user if self.user else 'Anonymous'} searched for '{self.query}'"
