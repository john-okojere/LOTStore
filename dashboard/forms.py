from django import forms
from shelf.models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'image', 'categories', 'price', 'size', 'stock', 'description', 'pay','delivery', 'productType', 'minBuy']
        widgets = {
            'categories': forms.CheckboxSelectMultiple,
            'size': forms.CheckboxSelectMultiple
        }
