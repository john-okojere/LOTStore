from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from . import views

urlpatterns = [
    path("register/",views.signup , name="register"),
    path('login/', auth_views.LoginView.as_view(template_name="account/login.html", redirect_authenticated_user=True), name="login" ),
    path('Login/', auth_views.LoginView.as_view(template_name="account/login.html", redirect_authenticated_user=True)),
    path('logout/', views.logout_view, name="logout" ),
    path('Logout/', views.logout_view),
    path("upload-profile-pic/", views.add_profilepic, name="upload"),

    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='account/password_reset_form.html',
        email_template_name='emails/password_reset_email.txt',
        subject_template_name='emails/password_reset_subject.txt',
        success_url=reverse_lazy('password_reset_done'),
    ), name='password_reset'),
    path('password-reset/sent/', auth_views.PasswordResetDoneView.as_view(
        template_name='account/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='account/password_reset_confirm.html',
        success_url=reverse_lazy('password_reset_complete'),
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='account/password_reset_complete.html',
    ), name='password_reset_complete'),
    path('password-change/', auth_views.PasswordChangeView.as_view(
        template_name='account/password_change.html',
        success_url=reverse_lazy('password_change_done'),
    ), name='password_change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='account/password_change_done.html',
    ), name='password_change_done'),

    path("edit-profile/",views.editprofile , name="editprofile"),
    path("Edit-Profile/",views.editprofile),
    path("add-about/",views.addAbout , name="AddAbout"),
    path("Add-About/",views.addAbout),
    path("edit-about/",views.EditAbout , name="editAbout"),
    path("edit-About/",views.EditAbout),
    path("<str:uid>/",views.profile , name="profile"),
]
