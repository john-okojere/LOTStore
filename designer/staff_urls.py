from django.urls import path
from . import views

app_name = "designer_staff"
urlpatterns = [
    path("", views.staff_list, name="list"),
    path("request/<uuid:uid>/", views.staff_detail, name="detail"),
    path("request/<uuid:uid>/action/", views.staff_action, name="action"),
    path("products/<uuid:product_uid>/mockups/", views.manage_mockups, name="mockups"),
    path("mockups/<int:pk>/delete/", views.delete_mockup, name="delete_mockup"),
]
