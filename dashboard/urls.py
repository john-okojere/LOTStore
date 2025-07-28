from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard, name='admin_dashboard'),

    #users
    path('all_users/', views.all_users, name='all_users'),
    path('all_staffs/', views.all_staffs, name='all_staffs'),
    path('api/edit_user/<int:user_id>/', views.edit_user, name='edit_user'),
    path('api/delete_user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('view_user/<int:user_id>/', views.view_user, name='view_user'),
    path('view_staff/<int:staff_id>/', views.view_staff, name='view_staff'),
    path('view_user/<int:user_id>/orders/', views.get_user_orders, name='get_user_orders'),
    path('view_user/<int:user_id>/cart/', views.get_user_cart, name='get_user_cart'),
    path('view_user/<int:user_id>/payments/', views.get_user_payments, name='get_user_payments'),

    # apis
    path('api/all_users/', views.api_all_users, name='api_all_users'),
    path('api/all_staff/', views.api_all_staff, name='api_all_staff'),

    #Order
    path("orders/", views.manage_orders, name="manage_orders"),
    path("orders/update/<int:order_id>/<str:status>/", views.update_order_status, name="update_order_status"),
    path('orders/detail/<int:order_id>/', views.order_detail, name='order_detail'),  # Add this line

    #Product
    
    path('categories/', views.product_category, name='category_list'),
    path('category/update/<int:category_id>/', views.update_category, name='update_category'),
    path('category/delete/<int:category_id>/', views.delete_category, name='delete_category'),
    path("category/add/", views.add_category, name="add_category"),

    path('size/', views.product_sizes, name='sizes_list'),
    path('size/update/<int:sizes_id>/', views.update_sizes, name='update_sizes'),
    path('size/delete/<int:sizes_id>/', views.delete_sizes, name='delete_sizes'),
    path("size/add/", views.add_sizes, name="add_sizes"),

    path('products/', views.product_list_view, name='product_list'),
    path('api/products/', views.product_list_api, name='product_list_api'),
    path('delete_product/<uuid:uid>/', views.delete_product, name='delete_product'),
    path("add-product", views.add_product, name="add-product"),
    path("edit-product/<uuid:uid>/", views.edit_product, name="edit-product"),
    path('product/<uuid:uid>/', views.product_detail_view, name='product_detail'),

    #traffic
    path('track-time-spent/', views.track_time_spent, name='track_time_spent'),
    path('track-add-to-cart/', views.track_add_to_cart, name='track_add_to_cart'),
]
