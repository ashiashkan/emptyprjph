from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()

class LoginForm(forms.Form):
    phone = forms.CharField(max_length=20, label='شماره موبایل')
    password = forms.CharField(widget=forms.PasswordInput, label='رمز عبور')

class RegisterForm(UserCreationForm):
    phone = forms.CharField(max_length=15, label='شماره موبایل')
    address = forms.CharField(widget=forms.Textarea, required=False, label='آدرس')
    language = forms.ChoiceField(
        choices=[('fa', 'فارسی'), ('en', 'English'), ('tr', 'Türkçe'), ('ar', 'العربية')],
        initial='fa',
        label='زبان'
    )
    
    class Meta:
        model = User
        fields = ['phone', 'password1', 'password2', 'address', 'language']

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if User.objects.filter(phone=phone).exists():
            raise forms.ValidationError("این شماره تلفن قبلاً ثبت شده است")
        return phone

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("رمزهای عبور مطابقت ندارند")
        return cleaned_data

class AddressForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['address']