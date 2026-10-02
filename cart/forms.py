from django import forms
from django.core.validators import RegexValidator
from .models import CartItem

NIGERIAN_STATES = [
    'Abia', 'Adamawa', 'Akwa Ibom', 'Anambra', 'Bauchi', 'Bayelsa', 'Benue', 'Borno',
    'Cross River', 'Delta', 'Ebonyi', 'Edo', 'Ekiti', 'Enugu', 'FCT - Abuja', 'Gombe',
    'Imo', 'Jigawa', 'Kaduna', 'Kano', 'Katsina', 'Kebbi', 'Kogi', 'Kwara', 'Lagos',
    'Nasarawa', 'Niger', 'Ogun', 'Ondo', 'Osun', 'Oyo', 'Plateau', 'Rivers', 'Sokoto',
    'Taraba', 'Yobe', 'Zamfara',
]


class AddToCartForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, label='Quantity')
    info = forms.CharField(max_length=255, label='Info', required=False)

    def __init__(self, *args, **kwargs):
        self.product = kwargs.pop('product')
        super().__init__(*args, **kwargs)
        self.sizes = list(self.product.size.all())
        for size in self.sizes:
            self.fields[f'size_{size.id}'] = forms.BooleanField(label=size.name, required=False)

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity')
        sizes_selected = [key for key, value in cleaned_data.items() if key.startswith('size_') and value]

        if self.sizes and not sizes_selected:
            raise forms.ValidationError("Please select a size.")
        if len(sizes_selected) > 1 and quantity == 1:
            raise forms.ValidationError("You cannot select more than one size if the quantity is one.")
        if quantity and self.product.productType == 'Min. Buy' and quantity < self.product.minBuy:
            raise forms.ValidationError(f"The minimum order for this item is {self.product.minBuy}.")
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


class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=255)
    address = forms.CharField(max_length=255)
    city = forms.CharField(max_length=100)
    state = forms.ChoiceField(choices=[(s, s) for s in NIGERIAN_STATES])
    phone_number = forms.CharField(
        max_length=20,
        validators=[RegexValidator(
            r'^(\+?\d{8,15}|0\d{10})$',
            "Enter a valid phone number, e.g. 08012345678 or +2348012345678.",
        )],
    )
    email = forms.EmailField()

    def clean_phone_number(self):
        return self.cleaned_data['phone_number'].replace(' ', '')

    def clean_full_name(self):
        return self.cleaned_data['full_name'].strip()
