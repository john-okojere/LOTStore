from django.urls import path
from . import views

app_name = "designer"
urlpatterns = [
    path("", views.design_list, name="list"),
    path("new/<uuid:product_uid>/", views.start_design, name="start"),
    path("<uuid:uid>/", views.design_detail, name="detail"),
    path("<uuid:uid>/editor/", views.editor, name="editor"),
    path("<uuid:uid>/save/", views.save_design, name="save"),
    path("<uuid:uid>/asset/", views.upload_asset, name="asset"),
    path("<uuid:uid>/submit/", views.submit_design, name="submit"),
    path("<uuid:uid>/quote/<str:decision>/", views.quote_decision, name="quote_decision"),
]
