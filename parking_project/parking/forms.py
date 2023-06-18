from django import forms
from django.core.validators import RegexValidator

class PaymentForm(forms.Form):
    stripe_token = forms.CharField(widget=forms.HiddenInput())