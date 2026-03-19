from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from .models import User, ProfilePic
from .forms import RegisterForm, EditRegisterForm

from django.contrib import messages
from django.contrib.auth import get_user_model
User = get_user_model()


def logout_view(request):
    logout(request)
    return redirect('/')

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

def signup(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            rform = form.save(commit=False)
            rform.save()
            email = form.cleaned_data.get('email')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(email=email, password=raw_password)
            
            # Create default profile picture
            image = "default/lg/avatar2.jpg"
            propic = ProfilePic.objects.create(user=user, image=image)
            propic.save()
            
            # Log the user in
            login(request, user)
            messages.success(request, f"New account created: {email}")
            
            # Send welcome email
            subject = "Welcome to LOTStore!"
            html_message = render_to_string('emails/welcome_email.html', {'user': user})
            plain_message = strip_tags(html_message)
            from_email = 'store@layersoftruth.org'
            to_email = email
            
            try:
                send_mail(subject, plain_message, from_email, [to_email], html_message=html_message)
            except Exception:
                # User creation should not fail when email delivery is unavailable.
                pass
            
            return redirect('/')
    else:
        form = RegisterForm()
    return render(request, 'account/register.html', {'form': form})


@login_required
def profile(request, uid):
    person = get_object_or_404(User, uid=uid)
    if request.user != person and not request.user.is_staff:
        return redirect('profile', uid=request.user.uid)
    profile_pic = getattr(person, 'profilepic', None)
    return render(request, 'account/index.html', {'person': person, 'profile_pic': profile_pic})

@login_required
def editprofile(request):
    if request.method == 'POST':
        form = EditRegisterForm(request.POST, instance = request.user)
        if form.is_valid():
            form.save()
            return redirect('profile', uid=request.user.uid)
    else:
        form = EditRegisterForm( instance = request.user)
    return render(request, 'account/edit.html', {'form': form})


from .forms import ProfileForm
@login_required
def add_profilepic(request):
    profile_pic, _ = ProfilePic.objects.get_or_create(
        user=request.user,
        defaults={'image': 'default/lg/avatar2.jpg'},
    )

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile_pic)
        if form.is_valid():
            c_form = form.save(commit=False)
            c_form.user = request.user
            c_form.save()

    return redirect('profile', uid=request.user.uid)


from .forms import BioForm
from .models import About

@login_required
def addAbout(request):
    if request.method == "POST":
        form = BioForm(request.POST)
        if form.is_valid():
            f = form.save(commit=False)
            f.user = request.user
            form.save()
            return redirect('profile', uid=request.user.uid)
    else:
        form = BioForm()
    return render(request, 'account/BioForm.html', {'form': form})


@login_required
def EditAbout(request):
    about = About.objects.get(user=request.user)
    if request.method == "POST":
        form = BioForm(request.POST, instance=about)
        if form.is_valid():
            f = form.save(commit=False)
            f.user = request.user
            form.save()
            return redirect('profile', uid=request.user.uid)
    else:
        form = BioForm(instance=about)
    return render(request, 'account/BioForm.html', {'form': form})
