from django.urls import path
from . import views

urlpatterns = [
    path("",views.homepage , name="homepage"),
    path("merchs/",views.merchs , name="merchs"),
    path("about/",views.about , name="about"),
    path("about",views.about),
    path("faq/",views.FAQ , name="faq"),
    path("faq",views.FAQ),
    path("return-policy/",views.returnPolicy , name="return-policy"),
    path("returnPolicy",views.returnPolicy),
    path("delivery-policy/",views.deliveryPolicy , name="delivery-policy"),
    path("deliveryPolicy",views.deliveryPolicy),
    path("privacy-policy/",views.privacyPolicy , name="privacy-policy"),
    path("privacyPolicy",views.privacyPolicy),
    path("terms-and-condition/",views.TermsCondition , name="TermsCondition"),
    path("Terms-&-Condition",views.TermsCondition),
    path("contact/",views.contact , name="contact"),
    path("contact",views.contact),
    path("details/<uuid:uid>/",views.details , name="details"),
    path("details/<uuid:uid>",views.details),

    path('filter/', views.filter_items, name='filter_items'),
    
    path('search/', views.search, name="search"),
    path('search', views.search),
    path('ss/', views.search_suggestions, name="search_suggestions" ),
    path('ss', views.search_suggestions),
    path('category/<str:cat>/', views.category_view, name="category"),
    path('category/<str:cat>', views.category_view),
]
