from django.contrib import admin
from .models import Cart, CartItem, Payment, Order, CartActivity

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1

class CartAdmin(admin.ModelAdmin):
    inlines = [CartItemInline]

admin.site.register(Cart, CartAdmin)

class PaymentAdmin(admin.ModelAdmin):
	list_display = ["id", "ref", 'amount', "verified", "date_created"]


admin.site.register(Payment, PaymentAdmin)

admin.site.register(Order)
admin.site.register(CartActivity)