from django import forms
from .models import CartItem

class AddToCartForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, label='Quantity')
    info = forms.CharField(max_length=255, label='Info', required=False)

    def __init__(self, *args, **kwargs):
        product = kwargs.pop('product')
        super().__init__(*args, **kwargs)
        for size in product.size.all():
            self.fields[f'size_{size.id}'] = forms.BooleanField(label=size.name, required=False)

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity')
        sizes_selected = [key for key, value in cleaned_data.items() if key.startswith('size_') and value]
        if len(sizes_selected) > 1 and quantity == 1:
            raise forms.ValidationError("You cannot select more than one size if the quantity is one.")
        return cleaned_data

    def clean_info(self):
        info = self.cleaned_data.get('info')
        if not info:
            info = ''  # Provide a default value if info is not provided
        return info


class UpdateCartItemForm(forms.ModelForm):
    class Meta:
        model = CartItem
        fields = ['quantity']
        widgets = {
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 0})
        }