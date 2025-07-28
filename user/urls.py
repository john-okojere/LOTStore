from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path("register/",views.signup , name="register"),
    path('Login/', LoginView.as_view(template_name="account/login.html"), name="login" ),
    path('Logout/', views.logout_view, name="logout" ),
    path("upload-profile-pic/", views.add_profilepic, name="upload"),

    path("Edit-Profile/",views.editprofile , name="editprofile"),
    path("Add-About/",views.addAbout , name="AddAbout"),
    path("edit-About/",views.EditAbout , name="editAbout"),
    path("<str:uid>/",views.profile , name="profile"),
]