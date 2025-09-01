from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

class LoginForm(forms.Form):
    phone = forms.CharField(max_length=20, label='شماره موبایل')
    password = forms.CharField(widget=forms.PasswordInput, label='رمز عبور')

class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label='رمز عبور')
    class Meta:
        model = User
        fields = ['phone', 'password', 'address', 'language']

class AddressForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['address']
