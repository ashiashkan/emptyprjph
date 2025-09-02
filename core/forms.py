from django import forms
from django.contrib.auth.models import User

class PhoneLoginForm(forms.Form):
    phone = forms.CharField(label="شماره تلفن", max_length=32)
    password = forms.CharField(label="رمز عبور", widget=forms.PasswordInput)

class RegisterForm(forms.Form):
    phone = forms.CharField(label="شماره تلفن", max_length=32)
    password = forms.CharField(label="رمز عبور", widget=forms.PasswordInput)
    confirm_password = forms.CharField(label="تکرار رمز عبور", widget=forms.PasswordInput)
    first_name = forms.CharField(label="نام", max_length=120, required=False)
    last_name = forms.CharField(label="نام خانوادگی", max_length=120, required=False)
    address = forms.CharField(label="آدرس", widget=forms.Textarea, required=False)

    def clean(self):
        cleaned = super().clean()
        p = cleaned.get('password')
        cp = cleaned.get('confirm_password')
        if p and cp and p != cp:
            raise forms.ValidationError("رمزها یکسان نیستند.")
        return cleaned

class AddressForm(forms.Form):
    first_name = forms.CharField(label="نام", max_length=120, required=False)
    last_name = forms.CharField(label="نام خانوادگی", max_length=120, required=False)
    address = forms.CharField(label="آدرس کامل", widget=forms.Textarea)
