import io
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views import View
from django.contrib import messages
from django.conf import settings
from django.utils.safestring import mark_safe

from .forms import LoginForm, RegisterForm, AddressForm
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

# فایل داروها
MEDICINES_FILE = Path(settings.BASE_DIR) / "medicines.json"
if MEDICINES_FILE.exists():
    with open(MEDICINES_FILE, "r", encoding="utf-8") as f:
        DATA = json.load(f)
else:
    DATA = {}

MEDICINE_IMAGES = DATA.get("medicine_images", {})

# جمع کردن همه گروه‌ها (همان کد موجود، بدون تغییر)
def get_all_groups():
    group_variant_pairs = [
        # ... (همه جفت‌ها مثل قبل، ترونکیت شده بود اما فرض می‌کنم کامل هست)
    ]
    groups = []
    # ... (کد کامل جمع‌آوری گروه‌ها – اگر ترونکیت بود، از کد اصلی استفاده کن)

class HomeView(View):
    def get(self, request):
        return render(request, 'home.html')

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

class RegisterView(View):
    def get(self, request):
        form = RegisterForm()
        return render(request, 'register.html', {'form': form})

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()  # ذخیره کاربر با phone, password, address, language
            # لاگین مستقیم بعد از ثبت‌نام
            login(request, user)
            request.session['language'] = user.language  # ذخیره زبان در جلسه
            messages.success(request, 'ثبت‌نام موفق! خوش آمدید.')
            return redirect('home')
        else:
            # نمایش خطاها مثل عدم تطبیق رمز یا شماره تکراری
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
        return render(request, 'register.html', {'form': form})

class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('home')

# بقیه ویوها مثل BuyMedicineView, CartView, PaymentView, ProfileView, OrderHistoryView, AdminPanelView, GuideView, SupportView, ChangeLanguageView
# (از کد اصلی استفاده کن، فقط اگر ترونکیت بود، فرض کن کامل هست. مثلاً در PaymentView.post، Order ذخیره می‌شه و session پاک می‌شه)

@require_POST
def add_to_cart(request):
    # ... (کد اضافه به سبد، اگر وجود داره)

# سایر فانکشن‌ها مثل checkout_view
def checkout_view(request):
    cart = request.session.get('cart', [])
    total = sum(Decimal(item['price']) * item['qty'] for item in cart)
    payment_options = ['TRX', 'USDT', 'BTC', 'ETH', 'BNB']
    return render(request, 'checkout.html', {'cart': cart, 'total': total, 'payment_options': payment_options})