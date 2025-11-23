from django import forms

from .models import Product


class ProductForm(forms.ModelForm):
    CATEGORY_CHOICES = [
        ('', '---------'),
        ('Vegetables', 'Vegetables'),
        ('Fruits', 'Fruits'),
    ]

    category = forms.ChoiceField(choices=CATEGORY_CHOICES, required=False)
    price = forms.DecimalField(label='Price per kilo', max_digits=10, decimal_places=2)

    class Meta:
        model = Product
        fields = ['name', 'category', 'price', 'stock_quantity', 'is_active']
        labels = {
            'stock_quantity': 'Stock (kg)',
        }


class StockUpdateForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['stock_quantity']
        labels = {
            'stock_quantity': 'Stock (kg)',
        }

