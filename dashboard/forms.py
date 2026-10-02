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

    def clean_price(self):
        price = self.cleaned_data['price']
        if price < 0:
            raise forms.ValidationError("Price cannot be negative.")
        return price

    def clean_stock(self):
        stock = self.cleaned_data['stock']
        if stock < 0:
            raise forms.ValidationError("Stock cannot be negative.")
        return stock

    def clean_minBuy(self):
        min_buy = self.cleaned_data['minBuy']
        if min_buy < 1:
            raise forms.ValidationError("Minimum buy must be at least 1.")
        return min_buy
