from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import RegexValidator
import re
User = get_user_model()

class LoginForm(forms.Form):
    phone = forms.CharField(
        max_length=20, 
        label='شماره موبایل',
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 
                   'شماره تلفن باید در قالب صحیح وارد شود. حداکثر 15 رقم مجاز است.')]
    )
    password = forms.CharField(widget=forms.PasswordInput, label='رمز عبور')


class RegisterForm(UserCreationForm):
    phone = forms.CharField(
        max_length=15, 
        label='شماره موبایل',
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 
                   'شماره تلفن باید در قالب صحیح وارد شود. حداکثر 15 رقم مجاز است.')]
    )
    first_name = forms.CharField(max_length=30, required=True, label='نام')
    last_name = forms.CharField(max_length=30, required=True, label='نام خانوادگی')
    email = forms.EmailField(required=False, label='ایمیل')
    address = forms.CharField(
        widget=forms.Textarea, 
        required=False, 
        label='آدرس',
        max_length=500,
        help_text='حداکثر 500 کاراکتر مجاز است'
    )
    language = forms.ChoiceField(
        choices=[('fa', 'فارسی'), ('en', 'English'), ('tr', 'Türkçe'), ('ar', 'العربية')],
        initial='fa',
        label='زبان'
    )
    
    class Meta:
        model = User
        fields = ['phone', 'first_name', 'last_name', 'email', 'password1', 'password2', 'address', 'language']

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if User.objects.filter(phone=phone).exists():
            raise forms.ValidationError("این شماره تلفن قبلاً ثبت شده است")
        
        # اعتبارسنجی فرمت شماره تلفن
        if not re.match(r'^\+?1?\d{9,15}$', phone):
            raise forms.ValidationError("شماره تلفن باید در قالب صحیح وارد شود. حداکثر 15 رقم مجاز است.")
        
        return phone


class ProfileUpdateForm(forms.ModelForm):
    phone = forms.CharField(
        max_length=15, 
        label='شماره موبایل',
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 
                   'شماره تلفن باید در قالب صحیح وارد شود. حداکثر 15 رقم مجاز است.')],
        disabled=True  # شماره تلفن قابل تغییر نیست
    )
    address = forms.CharField(
        widget=forms.Textarea, 
        required=False, 
        label='آدرس',
        max_length=500,
        help_text='حداکثر 500 کاراکتر مجاز است'
    )
    
    class Meta:
        model = User
        fields = ['phone', 'first_name', 'last_name', 'email', 'address', 'language']

class AddressForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['address']