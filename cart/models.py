from django.db import models
import uuid
from user.models import User
from shelf.models import Product, Sizes
import secrets
import random
import string
from .paystack  import  Paystack


class Cart(models.Model):
    uid = models.UUIDField( default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=25, default="0000")
    session_id = models.CharField(max_length=40, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    cleared = models.BooleanField(default=False)
    created_date = models.DateTimeField(auto_now=True, null=True)
    
    def __str__(self):
        return f"Cart for {self.user}"
    
    def generate_code(self):
        receipt_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=13))
        self.code = receipt_id
        return f'{self.code}'

    def save(self, *args, **kwargs):
        if not self.code or self.code == "0000":
            self.generate_code()
        return super().save(*args, **kwargs)


class CartItem(models.Model):
    uid = models.UUIDField( default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    size = models.ManyToManyField(Sizes)
    info = models.TextField( null=True, blank=True)
    quantity = models.PositiveIntegerField( default=0)
    created_date = models.DateTimeField(auto_now=True, null=True)

    def save(self, *args, **kwargs):
        if self.product.productType == "Single Buy":
            self.quantity = 1
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} in {self.cart}"

    def subtotal(self):
        return self.quantity * self.product.price


class Payment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    session_id = models.CharField(max_length=40, null=True, blank=True)
    amount = models.PositiveIntegerField()
    ref = models.CharField(max_length=200)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, null =True)
    email = models.EmailField()
    verified = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)

    # Shipping address fields
    full_name = models.CharField(max_length=255, null=True)
    address = models.CharField(max_length=255, null=True)
    city = models.CharField(max_length=100, null=True)
    state = models.CharField(max_length=100, null=True)
    phone_number = models.CharField(max_length=20, null=True)  # Adjust max length as needed
 

    class Meta:
        ordering = ('-date_created',)

    def __str__(self):
        return f"Payment: {self.amount}"

    def save(self, *args, **kwargs):
        while not self.ref:
            ref = secrets.token_urlsafe(16)
            object_with_similar_ref = Payment.objects.filter(ref=ref)
            if not object_with_similar_ref:
                self.ref = ref

        super().save(*args, **kwargs)

    def amount_value(self):
         return int(self.amount) * 102

    def verify_payment(self):
        paystack = Paystack()
        status, result = paystack.verify_payment(self.ref, self.amount)
        if status and isinstance(result, dict):
            if result.get('amount', 0) / 102 == self.amount:
                self.verified = True
            self.save()
        if self.verified:
            return True
        return False


class Order(models.Model):
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE)
    packed = models.BooleanField(default=False)
    sent = models.BooleanField(default=False)
    delivered = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)
     
    def __str__(self):
        return f'{self.payment}'
    

class CartActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.user if self.user else 'Anonymous'} added {self.product.name} to cart"
