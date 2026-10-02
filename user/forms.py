from django import forms
from .models import User, ProfilePic, About
from django.contrib.auth.forms import UserCreationForm


class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("first_name","last_name","phone","email","password1","password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email has been used already")
        return email
    

class EditRegisterForm(forms.ModelForm):
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    class Meta:
        model = User
        fields = ("first_name","last_name","phone","gender", "date_of_birth")
    

class ProfileForm(forms.ModelForm):
    MAX_UPLOAD_BYTES = 5 * 1024 * 1024

    class Meta:
        model = ProfilePic
        fields = ('image',)
        widgets = {'image': forms.ClearableFileInput(attrs={'accept': 'image/*'})}

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and getattr(image, 'size', 0) > self.MAX_UPLOAD_BYTES:
            raise forms.ValidationError("Image must be 5MB or smaller.")
        return image

class BioForm(forms.ModelForm):
    class Meta:
        model = About
        fields = ('country','state','address','about')