import io
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib import messages
from django.conf import settings
from django.utils.safestring import mark_safe
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.urls import reverse
from decimal import Decimal
import json
from pathlib import Path
import base64
import uuid
import qrcode
from io import BytesIO
from django.utils import timezone

from .forms import RegisterForm, AddressForm, LoginForm
from .models import CustomUser, Customer, Order, OrderItem, MEDICINES_DATA, TRANSLATIONS, MEDICINE_IMAGES

# لود medicines.json
MEDICINES_FILE = Path(settings.BASE_DIR) / "medicines.json"
if MEDICINES_FILE.exists():
    with open(MEDICINES_FILE, "r", encoding="utf-8") as f:
        DATA = json.load(f)
else:
    DATA = {}

MEDICINE_IMAGES = DATA.get("medicine_images", {})

# فانکشن کمکی برای ترجمه متن بر اساس زبان جلسه
def get_text(lang, key):
    return TRANSLATIONS.get(lang, {}).get(key, key)  # اگر ترجمه نبود، کلید رو برگردون

# جمع کردن همه گروه‌های داروها (کامل‌شده بر اساس گروه‌ها)
def get_all_groups():
    group_variant_pairs = [
        ("medicine_groups", "variants"),
        ("faroxy_groups", "faroxys"),
        ("tramadol_groups", "tramadols"),
        ("methadone_groups", "methadones"),
        ("methylphenidate_groups", "methylphenidates"),
        ("phyto_groups", "phytos"),
        ("seretide_groups", "seretides"),
        ("modafinil_groups", "modafinils"),
        ("monjaro_groups", "monjaros"),
        ("insuline_groups", "insulines"),
        ("soma_groups", "somas"),
        ("biobepa_groups", "biobepas"),
        ("warfarine_groups", "warfarines"),
        ("gardasil_groups", "gardasils"),
        ("rogam_groups", "rogams"),
        ("Aminoven_groups", "Aminovens"),
        ("Nexium_groups", "Nexiums"),
        ("Exelon_groups", "Exelons"),
        ("testestron_groups", "testestrons"),
        ("zithromax_groups", "zithromaxs"),
        ("Liskantin_groups", "Liskantins"),
        ("chimi_groups", "chimis"),
    ]

    groups = []
    for group_key, variant_key in group_variant_pairs:
        group_data = DATA.get(group_key, {})
        for g_name, g_info in group_data.items():
            variants = []
            for vid, v in g_info.get(variant_key, {}).items():
                vname = v.get("name_en") or vid
                vdesc = v.get("description_en", "")
                vprice = Decimal(v.get("price", 0))  # استفاده از Decimal برای دقت
                vimg = MEDICINE_IMAGES.get(vid, "")
                variants.append({
                    'id': vid,
                    'name': vname,
                    'description': vdesc,
                    'price': vprice,
                    'image': vimg
                })
            groups.append({
                'name': g_name,
                'variants': variants
            })
    return groups

# ویو صفحه اصلی
class HomeView(View):
    def get(self, request):
        return render(request, 'home.html')

# ویو ورود (با LoginForm)
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
                messages.success(request, get_text(request.session.get('language', 'fa'), 'welcome'))
                return redirect('home')
            else:
                messages.error(request, get_text(request.session.get('language', 'fa'), 'invalid_credentials'))
        return render(request, 'login.html', {'form': form})

# ویو ثبت‌نام (با لاگین خودکار)
class RegisterView(View):
    def get(self, request):
        form = RegisterForm()
        return render(request, 'register.html', {'form': form})

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            request.session['language'] = user.language
            messages.success(request, get_text(request.session.get('language', 'fa'), 'registration_success'))
            return redirect('home')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
        return render(request, 'register.html', {'form': form})

# ویو خروج
class LogoutView(View):
    def get(self, request):
        logout(request)
        messages.success(request, get_text(request.session.get('language', 'fa'), 'logout_success'))
        return redirect('home')

# ویو خرید دارو (نمایش گروه‌ها و واریانت‌ها)
class BuyMedicineView(View):
    def get(self, request):
        groups = get_all_groups()
        lang = request.session.get('language', 'fa')
        return render(request, 'buy_medicine.html', {'groups': groups, 'lang': lang})

# فانکشن اضافه به سبد خرید (با POST)
@require_POST
def add_to_cart(request):
    item_id = request.POST.get('item_id')
    qty = int(request.POST.get('qty', 1))
    groups = get_all_groups()
    item = None
    for group in groups:
        for variant in group['variants']:
            if variant['id'] == item_id:
                item = variant
                break
        if item:
            break
    if item:
        cart = request.session.get('cart', [])
        existing = next((i for i in cart if i['id'] == item_id), None)
        if existing:
            existing['qty'] += qty
        else:
            cart.append({
                'id': item_id,
                'name': item['name'],
                'price': str(item['price']),
                'qty': qty,
                'image': item['image']
            })
        request.session['cart'] = cart
        return JsonResponse({'success': True, 'total_items': len(cart)})
    return JsonResponse({'success': False}, status=400)

# ویو سبد خرید
class CartView(View):
    def get(self, request):
        cart = request.session.get('cart', [])
        total = sum(Decimal(item['price']) * item['qty'] for item in cart)
        return render(request, 'cart.html', {'cart': cart, 'total': total})

    def post(self, request):
        # برای آپدیت یا حذف (می‌تونی فانکشن‌های جدا اضافه کنی)
        pass

# ویو خلاصه سفارش
def checkout_view(request):
    cart = request.session.get('cart', [])
    if not cart:
        return redirect('cart')
    total = sum(Decimal(item['price']) * item['qty'] for item in cart)
    payment_options = ['TRX', 'USDT', 'BTC', 'ETH', 'BNB']
    return render(request, 'checkout.html', {'cart': cart, 'total': total, 'payment_options': payment_options})

# ویو پرداخت (ایجاد Order و QR کد)
class PaymentView(View):
    @method_decorator(login_required)
    def get(self, request):
        order_id = request.GET.get('order_id')
        order = get_object_or_404(Order, order_id=order_id, user=request.user)
        items = order.items.all()
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(order.deposit_address)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_code = base64.b64encode(buffered.getvalue()).decode()
        return render(request, 'payment.html', {'order': order, 'items': items, 'qr_code': qr_code})

    @method_decorator(login_required)
    def post(self, request):
        currency = request.POST.get('currency')
        cart = request.session.get('cart', [])
        if not cart:
            return redirect('cart')
        total = sum(Decimal(i['price']) * i['qty'] for i in cart)
        address_map = {
            'BTC': settings.BITCOIN_MAIN_WALLET,
            'ETH': settings.ETHEREUM_MAIN_WALLET,
            'TRX': settings.TRON_MAIN_WALLET,
            'USDT': settings.TRON_MAIN_WALLET,  # فرض برای USDT
            'BNB': settings.ETHEREUM_MAIN_WALLET,  # فرض برای BNB
        }
        deposit_address = address_map.get(currency, 'N/A')
        order = Order.objects.create(
            user=request.user,
            amount_usd=total,
            currency=currency,
            deposit_address=deposit_address,
            status='PENDING',
            metadata={'cart': cart}
        )
        # ذخیره آیتم‌ها
        for item in cart:
            OrderItem.objects.create(
                order=order,
                name=item['name'],
                unit_price=Decimal(item['price']),
                quantity=item['qty']
            )
        request.session['cart'] = []  # خالی کردن سبد
        messages.success(request, get_text(request.session.get('language', 'fa'), 'payment_success'))
        return redirect(reverse('payment') + f'?order_id={order.order_id}')

# ویو پروفایل
class ProfileView(View):
    @method_decorator(login_required)
    def get(self, request):
        form = AddressForm(instance=request.user)
        return render(request, 'profile.html', {'form': form})

    @method_decorator(login_required)
    def post(self, request):
        form = AddressForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, get_text(request.session.get('language', 'fa'), 'profile_updated'))
            return redirect('profile')
        return render(request, 'profile.html', {'form': form})

# ویو تاریخچه سفارشات
class OrderHistoryView(View):
    @method_decorator(login_required)
    def get(self, request):
        orders = Order.objects.filter(user=request.user).order_by('-created_at')
        return render(request, 'order_history.html', {'orders': orders})

# ویو پنل ادمین
class AdminPanelView(View):
    @method_decorator(login_required)
    def get(self, request):
        if not request.user.is_superuser:
            messages.error(request, get_text(request.session.get('language', 'fa'), 'access_denied'))
            return redirect('home')
        orders = Order.objects.all().order_by('-created_at')
        return render(request, 'admin_panel.html', {'orders': orders})

# ویو راهنما
class GuideView(View):
    def get(self, request):
        return render(request, 'guide.html')

# ویو پشتیبانی
class SupportView(View):
    def get(self, request):
        return render(request, 'support.html')

# ویو تغییر زبان
class ChangeLanguageView(View):
    def post(self, request):
        lang = request.POST.get('lang', 'fa')
        request.session['language'] = lang
        if request.user.is_authenticated:
            request.user.language = lang
            request.user.save(update_fields=['language'])
        messages.success(request, get_text(lang, 'language_changed'))
        return redirect('home')