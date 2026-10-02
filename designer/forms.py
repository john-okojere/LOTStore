from django import forms
from .models import ProductMockupView


class MockupViewForm(forms.ModelForm):
    class Meta:
        model = ProductMockupView
        fields = ("name", "image", "print_x", "print_y", "print_width", "print_height", "output_width", "output_height", "position")

