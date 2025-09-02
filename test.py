import io
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views import View
from django.contrib import messages
from django.conf import settings
from django.utils.safestring import mark_safe

from .forms import RegisterForm, AddressForm, LoginForm  # PhoneLoginForm رو حذف کن – فقط LoginForm

from .models import Order, MEDICINES_DATA, TRANSLATIONS, MEDICINE_IMAGES
import json
from pathlib import Path
from django.http import JsonResponse
from decimal import Decimal
import qrcode
from io import BytesIO
import base64
from django.utils import timezone
from django.views.decorators.http import require_POST

# بقیه کد views.py مثل قبل (HomeView, LoginView, etc.)
# در LoginView، از form = LoginForm() استفاده کن، نه PhoneLoginForm
class LoginView(View):
    def get(self, request):
        form = LoginForm()
        return render(request, 'login.html', {'form': form})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data['phone']
            password = form.cleaned_data['password']
            user = authenticate(request, phone=phone, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, 'خوش آمدید!')
                return redirect('home')
            else:
                messages.error(request, 'شماره موبایل یا رمز عبور اشتباه است.')
        return render(request, 'login.html', {'form': form})

# بقیه ویوها مثل RegisterView (که از RegisterForm استفاده می‌کنه) بدون تغییر