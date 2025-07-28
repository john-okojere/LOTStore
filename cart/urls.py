from django.urls import path
from . import views

urlpatterns = [
    path('add-to-cart/<uuid:product_uid>/', views.add_to_cart, name='add_to_cart'),
    path('view-cart/', views.view_cart, name='view_cart'),
    path('delete_from_cart/<uuid:cart_item_uid>/', views.delete_from_cart, name='delete_from_cart'),
    path('update/<uuid:cart_item_uid>/<str:action>/', views.update_cart_quantity, name='update_cart_quantity'),
    
	path('initiate-payment/', views.initiate_payment, name='initiate_payment'),
	path('payment/<str:ref>/', views.verify_payment, name='verify_payment'),

	path('payment-view/<str:ref>/', views.viewpayment, name='payment_view'),
	path('payment-history/', views.payment_history, name='payment_history'),

	path('Delivery-Sent/', views.sent_order, name='sent_order'),
	path('Delivered/', views.order_delivered, name='order_delivered'),
    
	path('sm/', views.sm, name=''),
]
