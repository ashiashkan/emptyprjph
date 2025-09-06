from pathlib import Path
import json
from urllib import request
import uuid
import time
import threading
from decimal import Decimal
from io import BytesIO
import hashlib

# خارجی‌ها — در صورت عدم نصب، توابع جایگزین سبک استفاده می‌شوند
try:
    import qrcode
except Exception:
    qrcode = None

try:
    import requests
except Exception:
    requests = None

# Web3 / Tron (فقط تلاش برای وارد کردن؛ در غیر اینصورت از fallback استفاده می‌شود)
try:
    from web3 import Web3, HTTPProvider as Web3HTTPProvider
except Exception:
    Web3 = None
    Web3HTTPProvider = None

try:
    from tronpy import Tron
    from tronpy.providers import HTTPProvider as TronHTTPProvider
except Exception:
    Tron = None
    TronHTTPProvider = None

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
import csv

from .models import CustomUser, Order, OrderItem, Cart, CartItem, Customer
from .forms import LoginForm, RegisterForm, ProfileUpdateForm

import requests
from decimal import Decimal
from django.views.decorators.csrf import csrf_exempt




# اگر فرم AddressForm جداگانه وجود نداشت، از فرم پروفایل به عنوان fallback استفاده می‌کنیم
try:
    from .forms import AddressForm
except Exception:
    AddressForm = ProfileUpdateForm

# تنظیمات مدیریت (فراخوانی از settings یا مقدار پیش‌فرض)
ADMIN_USERNAME = getattr(settings, "ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = getattr(settings, "ADMIN_PASSWORD_HASH", None)

def hash_password(password: str) -> str:
    # هَش ساده SHA256 به عنوان fallback؛ توصیه می‌شود از مکانیزم امن‌تر استفاده شود
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def buy_medicine(request):
    query = request.GET.get('q', '').strip()
    groups = []
    mgroups = MEDICINES_DATA.get('medicine_groups', {})
    
    # اگر medicine_groups یک دیکشنری است، آن را به لیست تبدیل می‌کنیم
    if isinstance(mgroups, dict):
        mgroups = mgroups.values()
    
    for group in mgroups:
        group_name = group.get('name', 'Unknown Group')
        variants = group.get('variants', [])
        
        # اگر variants یک دیکشنری است، به لیست تبدیل می‌کنیم
        if isinstance(variants, dict):
            variants = list(variants.values())
        
        # اطمینان از وجود ID برای هر variant
        processed_variants = []
        for variant in variants:
            # اگر variant فاقد ID است، یک ID منحصر به فرد ایجاد کنید
            if 'id' not in variant or not variant['id']:
                variant = variant.copy()  # ایجاد کپی برای جلوگیری از تغییر داده اصلی
                variant['id'] = str(uuid.uuid4())
            processed_variants.append(variant)
        
        variants = processed_variants
        
        if query:
            # فیلتر کردن variants بر اساس query
            filtered_variants = []
            for variant in variants:
                name = variant.get('name', '')
                description = variant.get('description', '')
                if query.lower() in name.lower() or query.lower() in description.lower():
                    filtered_variants.append(variant)
            variants = filtered_variants
        
        groups.append({
            'key': group.get('id', str(uuid.uuid4())),
            'name': group_name,
            'variants': variants
        })
    
    return render(request, 'buy_medicine.html', {'groups': groups, 'query': query})

def get_exchange_rates():
    """
    Try to fetch rates from CoinGecko (if requests available), otherwise return safe fallbacks.
    Returns mapping like {'BTC': {'USD': Decimal('50000')}, ...}
    """
    try:
        if requests:
            resp = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids":"bitcoin,ethereum,binancecoin,tron,toncoin,tether","vs_currencies":"usd"},
                timeout=5,
            )
            data = resp.json()
            def _usd(key, fallback):
                return Decimal(str(data.get(key, {}).get('usd', fallback)))
            return {
                'BTC': {'USD': _usd('bitcoin', 50000)},
                'ETH': {'USD': _usd('ethereum', 3000)},
                'BNB': {'USD': _usd('binancecoin', 500)},
                'TRX': {'USD': _usd('tron', 0.12)},
                'TON': {'USD': _usd('toncoin', 2.5)},
                'USDT': {'USD': Decimal('1')},
            }
    except Exception:
        pass

    # fallback static rates
    return {
        'BTC': {'USD': Decimal('50000')},
        'ETH': {'USD': Decimal('3000')},
        'BNB': {'USD': Decimal('500')},
        'TRX': {'USD': Decimal('0.12')},
        'TON': {'USD': Decimal('2.5')},
        'USDT': {'USD': Decimal('1')},
    }


def medicine_detail(request, item_id):
    # جستجوی آیتم در تمام گروه‌ها
    for group in MEDICINES_DATA.get('medicine_groups', {}).values():
        variants = group.get('variants', [])
        if isinstance(variants, dict):
            variants = list(variants.values())
        
        for variant in variants:
            # اطمینان از تطابق رشته‌ای
            if str(variant.get('id', '')) == str(item_id):
                return render(request, 'medicine_detail.html', {'item': variant})
    
    messages.error(request, 'محصول مورد نظر یافت نشد')
    return redirect('buy_medicine')

# بارگذاری medicines.json به صورت گلوبال و نرمال‌سازی ساختار گروه‌ها
MEDICINES_FILE = Path(settings.BASE_DIR) / "medicines.json"
MEDICINES_DATA = {}
TRANSLATIONS = {}
MEDICINE_IMAGES = {}


def _normalize_medicine_groups(raw_groups):
    """Normalize different possible shapes of groups into a dict of groups where
    each group has a 'variants' dict mapping variant_id -> variant dict.
    Handles cases where products are stored directly as keys inside a group
    (common in the provided medicines.json) or under an explicit 'variants' key.
    """
    out = {}
    if not raw_groups:
        return out

    # if a list was provided, convert to dict using provided id or generated uuid
    if isinstance(raw_groups, list):
        g_iter = {str(g.get('id') or uuid.uuid4()): g for g in raw_groups}
    else:
        g_iter = dict(raw_groups)

    # metadata keys that are not variants
    meta_keys = {'id', 'name', 'name_en', 'name_fa', 'name_tr', 'name_ar', 'exp', 'description',
                 'description_en', 'description_fa', 'description_tr', 'description_ar', 'variants'}

    for gid, group in g_iter.items():
        if not isinstance(group, dict):
            continue
        grp = dict(group)  # shallow copy

        # collect variants
        variants = {}

        # 1) explicit 'variants' key takes precedence
        if 'variants' in grp and grp.get('variants'):
            v = grp.get('variants')
            if isinstance(v, list):
                for vv in v:
                    if not isinstance(vv, dict):
                        continue
                    vid = str(vv.get('id') or uuid.uuid4())
                    vv = vv.copy()
                    vv['id'] = vid
                    variants[vid] = vv
            elif isinstance(v, dict):
                for k, vv in v.items():
                    if not isinstance(vv, dict):
                        continue
                    vid = str(vv.get('id') or k)
                    vv = vv.copy()
                    vv['id'] = vid
                    variants[vid] = vv

        # 2) fallback: treat any child dict that isn't metadata as a variant
        for key, val in group.items():
            if key in meta_keys:
                continue
            if isinstance(val, dict):
                vid = str(val.get('id') or key or uuid.uuid4())
                vcopy = val.copy()
                vcopy['id'] = vid
                # fill name if missing using key
                if not vcopy.get('name') and isinstance(key, str):
                    vcopy['name'] = key
                variants[vid] = vcopy

        # ensure variants is a dict
        grp['variants'] = variants
        out[str(gid)] = grp

    return out


if MEDICINES_FILE.exists():
    try:
        with open(MEDICINES_FILE, "r", encoding="utf-8") as f:
            medicine_data = json.load(f)

        # store raw data
        MEDICINES_DATA.update(medicine_data or {})

        # load translations and images if present (support both 'images' and 'medicine_images')
        TRANSLATIONS.update(medicine_data.get('translations', {}) or {})
        MEDICINE_IMAGES.update(medicine_data.get('images', {}) or {})
        MEDICINE_IMAGES.update(medicine_data.get('medicine_images', {}) or {})

        # normalize medicine_groups into a dict of groups each with a 'variants' dict
        raw_mg = MEDICINES_DATA.get('medicine_groups', {})
        MEDICINES_DATA['medicine_groups'] = _normalize_medicine_groups(raw_mg)

    except Exception as e:
        print(f"Error loading medicine data: {e}")




@login_required
def payment_page(request):
        WALLETS = {
    'TRX': 'TW88rRvvvoo3dRpippmQJUNmowdmgaCjhE',
    'USDT': 'TW88rRvvvoo3dRpippmQJUNmowdmgaCjhE',
    'BTC': 'bc1qwc2lqwjxwc29tnxn6p2kstsrqcc0ems5957r5m',
    'BNB': '0xaF99374Dd015dA244cdA1F1Fc2183b423a17A10D',
    'ETH': '0xaF99374Dd015dA244cdA1F1Fc2183b423a17A10D',
    'TON': 'UQATaVtLxM93Sms6jNJwrMjQ_UOKTOvR2niXyS6ONIkx2HNc',
    }



# تابع کمکی ترجمه/متن
def get_text(lang, key, **kwargs):
    translations = {
        'en': {
            'home': 'Home',
            'logout': 'Logout',
            'cart': 'Cart',
            'order_history': 'Order History',
            'guide': 'Guide',
            'support': 'Support',
            'profile': 'Profile',
            'change_language': 'Change Language',
            'logout_success': 'Logout successful',
            'logout_blocked': 'For spam prevention, logout is blocked for {minutes} minutes',
            'cart_empty': 'Your cart is empty',
            'item_summary': '{item_name} x {item_qty} - {item_price}',
            'remove': 'Remove',
            'total_amount': 'Total amount: {total}',
            'checkout': 'Checkout',
            'register_first': 'Please register first',
            'buying_guide': 'Detailed buying guide in English...',
            'support_text': 'Support text in English...',
            'payment_success': 'Payment successful',
        },
        'fa': {
            'home': 'خانه',
            'logout': 'خروج',
            'cart': 'سبد خرید',
            'order_history': 'تاریخچه سفارشات',
            'guide': 'راهنما',
            'support': 'پشتیبانی',
            'profile': 'پروفایل',
            'change_language': 'تغییر زبان',
            'logout_success': 'خروج موفق',
            'logout_blocked': 'برای جلوگیری از اسپم، تا {minutes} دقیقه امکان خروج ندارید',
            'cart_empty': 'سبد خرید خالی است',
            'item_summary': '{item_name} x {item_qty} - {item_price}',
            'remove': 'حذف',
            'total_amount': 'مجموع مبلغ: {total}',
            'checkout': 'پرداخت',
            'register_first': 'ابتدا ثبت‌نام کنید',
            'buying_guide': 'راهنمای خرید به فارسی...',
            'support_text': 'متن پشتیبانی به فارسی...',
            'payment_success': 'پرداخت موفق',
        }
    }
    # اگر ترجمه در فایل medicines.json موجود است، از آن استفاده کن
    t = TRANSLATIONS.get(lang, {})
    if key in t:
        return t[key].format(**kwargs)
    # fallback به جیسون بالا
    return translations.get(lang, translations['en']).get(key, key).format(**kwargs)


# =========================
# توابع تولید آدرس‌های دریافتی (fallback ساده در صورت نبود لایبرری‌ها)
# =========================
def generate_btc_address():
    # اگر bitcoinlib نصب باشد می‌توان از آن استفاده کرد، در غیر این صورت یک آدرس ساختگی با uuid برمی‌گردانیم
    try:
        from bitcoinlib.wallets import wallet_create_or_open
        w = wallet_create_or_open('pharma_wallet', network='bitcoin')
        return w.get_key().address
    except Exception:
        return "btc_" + uuid.uuid4().hex


def generate_eth_address():
    if Web3 and Web3HTTPProvider:
        try:
            w3 = Web3(Web3HTTPProvider('https://mainnet.infura.io/v3/YOUR_INFURA_KEY'))
            account = w3.eth.account.create()
            return account.address
        except Exception:
            pass
    # fallback ساختگی
    return "0x" + uuid.uuid4().hex[:40]


def generate_trx_address():
    if Tron and TronHTTPProvider:
        try:
            client = Tron(TronHTTPProvider('https://api.trongrid.io'))
            acc = client.generate_address()
            # tronpy generate returns dict with address info in some versions
            if isinstance(acc, dict):
                return acc.get("base58") or acc.get("address") or str(acc)
            return str(acc)
        except Exception:
            pass
    return "TRX" + uuid.uuid4().hex[:30]


# =========================
# بررسی پرداخت (ساده شده و ایمن‌تر)
# =========================
def check_btc_payment(address, amount):
    # placeholder: اگر بخواهید از API واقعی استفاده کنید اینجا فراخوانی شود
    # در این پیاده‌سازی فقط False برمی‌گردد
    return False


def check_payment(user, cart_items, total, addresses, lang):
    """
    این تابع در تِرِد اجرا می‌شود. پارامتر cart_items و total را از session یا caller بگیرید
    تا نیازی به دسترسی به request داخل ترد نباشد.
    """
    max_checks = 30
    for _ in range(max_checks):
        # نمونه برای BTC (شبیه‌سازی)
        if check_btc_payment(addresses.get('btc'), total):
            # ایجاد سفارش در دیتابیس
            try:
                order = Order.objects.create(
                    user=user,
                    total_amount=Decimal(total),
                    currency='BTC',
                    status='PAID',
                    crypto_address=addresses.get('btc')
                )
                # در صورت نیاز، ایجاد OrderItemها از cart_items
                for it in cart_items:
                    OrderItem.objects.create(
                        order=order,
                        product_id=it.get('id'),
                        name=it.get('name'),
                        price=Decimal(it.get('price') or 0),
                        quantity=int(it.get('qty') or 1)
                    )
            except Exception as e:
                print("Error creating order after payment:", e)
            break
        time.sleep(60)


# =========================
# کلاس‌ها و ویوها (ساختار حفظ شده)
# =========================
class HomeView(View):
    def get(self, request):
        lang = request.session.get('language', 'fa')
        selected = request.GET.get('selected', get_text(lang, 'home'))
        if request.user.is_authenticated:
            if selected == get_text(lang, 'logout'):
                return self.logout(request)
            elif selected == get_text(lang, 'cart'):
                return CartView().get(request)
            elif selected == get_text(lang, 'order_history'):
                return OrderHistoryView().get(request)
            elif selected == get_text(lang, 'guide'):
                return GuideView().get(request)
            elif selected == get_text(lang, 'support'):
                return SupportView().get(request)
            elif selected == get_text(lang, 'profile'):
                return ProfileView().get(request)
            elif selected == get_text(lang, 'change_language'):
                return ChangeLanguageView().get(request)
        return render(request, 'home.html', {'lang': lang})

    def logout(self, request):
        lang = request.session.get('language', 'fa')
        phone = getattr(request.user, "phone", None)
        allowed, remaining = check_logout_spam(phone) if phone else (True, 0)
        if allowed:
            user = request.user
            # اطمینان از نوع داده logout_history
            hist = getattr(user, "logout_history", []) or []
            hist.append(time.time())
            user.logout_history = hist
            user.save()
            logout(request)
            request.session.flush()
            messages.success(request, get_text(lang, 'logout_success'))
            return redirect('login')
        else:
            messages.error(request, get_text(lang, 'logout_blocked', minutes=remaining))
            return redirect('home')


class LoginView(View):
    def get(self, request):
        form = LoginForm()
        return render(request, 'login.html', {'form': form})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data['phone']
            password = form.cleaned_data['password']
            if ADMIN_PASSWORD_HASH and phone == ADMIN_USERNAME and hash_password(password) == ADMIN_PASSWORD_HASH:
                user, created = CustomUser.objects.get_or_create(username=ADMIN_USERNAME, defaults={'is_superuser': True, 'is_staff': True})
                login(request, user)
                return redirect('admin_panel')
            user = authenticate(username=phone, password=password)
            if user:
                login(request, user)
                request.session['language'] = getattr(user, "language", request.session.get('language', 'fa'))
                return redirect('home')
        messages.error(request, _('Invalid credentials'))
        return render(request, 'login.html', {'form': form})


class RegisterView(View):
    def get(self, request):
        form = RegisterForm()
        return render(request, 'register.html', {'form': form})

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = form.cleaned_data.get('phone', str(uuid.uuid4()))
            user.set_password(form.cleaned_data.get('password'))
            user.save()
            login(request, user)
            request.session['language'] = getattr(user, "language", 'fa')
            return redirect('home')
        return render(request, 'register.html', {'form': form})


class AdminPanelView(View):
    def get(self, request):
        if not request.user.is_superuser:
            return redirect('login')
        users = CustomUser.objects.all()
        orders = Order.objects.all()
        search_term = request.GET.get('search', '')
        if search_term:
            users = users.filter(phone__icontains=search_term) | users.filter(address__icontains=search_term)
            orders = orders.filter(user__phone__icontains=search_term)
        stats = {
            'total_users': users.count(),
            'total_orders': orders.count(),
        }
        return render(request, 'admin_panel.html', {'users': users, 'orders': orders, 'stats': stats})


class BuyMedicineView(View):
    def get(self, request):
        lang = request.session.get('language', 'fa')
        groups = []
        mgroups = MEDICINES_DATA.get('medicine_groups', {})
        for gid, group in mgroups.items():
            gname = group.get(f'name_{lang}', group.get('name', group.get('name_en', gid)))
            variants = group.get('variants', {}) or {}
            # if variants is list convert to dict by id
            if isinstance(variants, list):
                vmap = {}
                for v in variants:
                    vid = v.get('id') or str(uuid.uuid4())
                    vmap[str(vid)] = v
                variants = vmap
            # localize variants
            vlist = []
            for variant_id, variant in variants.items():
                v = variant.copy()
                v['name'] = v.get(f'name_{lang}', v.get('name_en', v.get('name', '')))
                v['description'] = v.get(f'description_{lang}', v.get('description_en', v.get('description', '')))
                v['id'] = variant_id
                vlist.append(v)
            groups.append({'id': gid, 'name': gname, 'variants': vlist})
        return render(request, 'buy_medicine.html', {'groups': groups, 'lang': lang})

    def post(self, request):
        variant_id = request.POST.get('variant_id')
        qty = int(request.POST.get('qty', 1))
        found = False
        mgroups = MEDICINES_DATA.get('medicine_groups', {})
        for group in mgroups.values():
            variants = group.get('variants', {}) or {}
            if isinstance(variants, list):
                for v in variants:
                    if str(v.get('id')) == str(variant_id):
                        item = v
                        found = True
                        break
            else:
                if str(variant_id) in variants:
                    item = variants[variant_id]
                    found = True
            if found:
                break
        if found:
            cart = request.session.get('cart', [])
            cart.append({
                'id': str(variant_id),
                'name': item.get('name') or item.get('name_en'),
                'price': item.get('price') or 0,
                'qty': qty
            })
            request.session['cart'] = cart
            return redirect('cart')
        else:
            messages.error(request, _('Item not found'))
            return redirect('buy_medicine')


class CartView(View):
    def get(self, request):
        lang = request.session.get('language', 'fa')
        cart = request.session.get('cart', [])
        if not cart:
            return render(request, 'cart.html', {'message': get_text(lang, 'cart_empty')})
        total = sum(int(item.get('qty', 1)) * float(item.get('price', 0)) for item in cart)
        for item in cart:
            item['name'] = item.get('name', 'Item')
            item['price'] = float(item.get('price', 0))
            item['qty'] = int(item.get('qty', 1))
        if request.session.get('checkout_active', False):
            return PaymentView().get(request, total=total)
        return render(request, 'cart.html', {'cart': cart, 'total': total})

    def post(self, request):
        lang = request.session.get('language', 'fa')
        cart = request.session.get('cart', [])
        action = request.POST.get('action')
        if action == 'remove':
            try:
                i = int(request.POST.get('index'))
                if 0 <= i < len(cart):
                    del cart[i]
            except Exception:
                pass
        elif action == 'checkout':
            if not getattr(request.user, "address", None):
                messages.warning(request, get_text(lang, 'register_first'))
                return redirect('profile')
            request.session['checkout_active'] = True
            return redirect('cart')
        request.session['cart'] = cart
        return redirect('cart')


class PaymentView(View):
    def get(self, request, total=None):
        if total is None:
            try:
                total = float(request.GET.get('total', 0))
            except Exception:
                total = 0.0
        lang = request.session.get('language', 'fa')
        addresses = {
            'btc': generate_btc_address(),
            'eth': generate_eth_address(),
            'trx': generate_trx_address(),
        }
        qr_codes = {}
        for crypto, address in addresses.items():
            if qrcode:
                try:
                    qr = qrcode.make(address)
                    buf = BytesIO()
                    qr.save(buf, format='PNG')
                    qr_codes[crypto] = buf.getvalue()
                except Exception:
                    qr_codes[crypto] = None
            else:
                qr_codes[crypto] = None

        # شروع ترد بررسی پرداخت با انتقال داده‌های لازم
        cart = request.session.get('cart', [])
        threading.Thread(target=check_payment, args=(request.user, cart, total, addresses, lang), daemon=True).start()
        return render(request, 'payment.html', {'total': total, 'addresses': addresses, 'qr_codes': qr_codes, 'lang': lang})


# توابع کمکی برای کنترل اسپم خروج
def check_logout_spam(phone):
    if not phone:
        return True, 0
    try:
        user = CustomUser.objects.get(phone=phone)
    except CustomUser.DoesNotExist:
        return True, 0
    hist = getattr(user, "logout_history", []) or []
    if hist:
        last_logout = max(hist)
        if time.time() - last_logout < 300:  # 5 دقیقه
            remaining = 5 - int((time.time() - last_logout) / 60)
            return False, max(1, remaining)
    return True, 0


class ProfileView(View):
    def get(self, request):
        lang = request.session.get('language', 'fa')
        form = AddressForm(instance=request.user)
        return render(request, 'profile.html', {'form': form, 'user': request.user, 'lang': lang})

    def post(self, request):
        form = AddressForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _('Profile updated'))
            return redirect('profile')
        return render(request, 'profile.html', {'form': form, 'user': request.user})


class OrderHistoryView(View):
    def get(self, request):
        lang = request.session.get('language', 'fa')
        orders = Order.objects.filter(user=request.user)
        return render(request, 'order_history.html', {'orders': orders, 'lang': lang})


class GuideView(View):
    def get(self, request):
        lang = request.session.get('language', 'fa')
        text = get_text(lang, 'buying_guide')
        return render(request, 'guide.html', {'text': text})


class SupportView(View):
    def get(self, request):
        lang = request.session.get('language', 'fa')
        text = get_text(lang, 'support_text')
        return render(request, 'support.html', {'text': text})


class ChangeLanguageView(View):
    def get(self, request):
        request.session.pop('language', None)
        return redirect('home')

    def post(self, request):
        lang = request.POST.get('lang')
        if lang in ['fa', 'en', 'tr', 'ar']:
            request.session['language'] = lang
            if request.user.is_authenticated:
                request.user.language = lang
                request.user.save()
        return redirect('home')


class LogoutView(View):
    def get(self, request):
        return HomeView().logout(request)


# =========================
# توابع تابعی (تنظیم‌شده و غیر تکراری)
# =========================
def home(request):
    return render(request, 'home.html')


def guide(request):
    return render(request, 'guide.html')


def support(request):
    return render(request, 'support.html')




def medicine_detail(request, item_id):
    item = None
    mgroups = MEDICINES_DATA.get('medicine_groups', {})
    for group_data in mgroups.values():
        variants = group_data.get('variants', []) or []
        vlist = variants if isinstance(variants, list) else list(variants.values())
        for variant in vlist:
            if str(variant.get('id')) == str(item_id):
                item = variant
                break
        if item:
            break

    if not item:
        messages.error(request, 'محصول مورد نظر یافت نشد')
        return redirect('buy_medicine')

    return render(request, 'medicine_detail.html', {'item': item})


def view_cart(request):
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart = Cart.objects.filter(session_key=session_key).first()

    items = cart.items.all() if cart else []
    total = sum(item.price * item.quantity for item in items) if items else 0
    return render(request, 'cart.html', {'items': items, 'total': total})


def cart_view(request):
    return render(request, 'cart.html')


def cart_add(request, item_id):
    qty = int(request.POST.get('qty', 1))
    if qty < 1:
        qty = 1

    product = None
    mgroups = MEDICINES_DATA.get('medicine_groups', {})
    for group in mgroups.values():
        variants = group.get('variants', []) or []
        vlist = variants if isinstance(variants, list) else list(variants.values())
        for variant in vlist:
            if str(variant.get('id')) == str(item_id):
                product = variant
                break
        if product:
            break

    if not product:
        messages.error(request, "محصول یافت نشد.")
        return redirect('buy_medicine')

    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, _ = Cart.objects.get_or_create(session_key=session_key)

    item, created = CartItem.objects.get_or_create(
        cart=cart, product_id=item_id,
        defaults={'name': product.get('name'), 'price': Decimal(str(product.get('price', 0))), 'quantity': qty}
    )
    if not created:
        item.quantity += qty
        item.save()

    messages.success(request, "محصول به سبد اضافه شد.")
    return redirect('view_cart')


def cart_update(request, item_id):
    messages.success(request, 'سبد خرید به روزرسانی شد')
    return redirect('cart')


@login_required
def checkout(request):
    if not request.user.is_authenticated:
        messages.error(request, 'برای ادامه خرید باید وارد حساب کاربری خود شوید')
        return redirect('login')

    raw_cart = request.session.get('cart', [])
    # support both dict {id: {...}} and list [{id:..., qty:..., price:...}, ...]
    cart_list = []
    if isinstance(raw_cart, dict):
        for item_id, item_data in raw_cart.items():
            cart_list.append({
                'id': str(item_id),
                'qty': int(item_data.get('qty', 1)),
                'price': float(item_data.get('price', 0)),
            })
    elif isinstance(raw_cart, list):
        # ensure normalized items
        for it in raw_cart:
            cart_list.append({
                'id': str(it.get('id')),
                'qty': int(it.get('qty', 1)),
                'price': float(it.get('price', 0)),
            })

    if not cart_list:
        messages.error(request, 'سبد خرید شما خالی است')
        return redirect('buy_medicine')

    total_amount = sum(it['qty'] * it['price'] for it in cart_list)

    # build cart_items for display by resolving product meta where possible
    cart_items = []
    for it in cart_list:
        product_name = it.get('id')
        # find product in MEDICINES_DATA (best-effort)
        for group in MEDICINES_DATA.get('medicine_groups', {}).values():
            variants = group.get('variants', {}) or {}
            vlist = variants if isinstance(variants, list) else list(variants.values())
            for variant in vlist:
                if str(variant.get('id')) == str(it['id']):
                    product_name = variant.get('name_fa') or variant.get('name_en') or variant.get('name') or product_name
                    break
            if product_name != it.get('id'):
                break

        cart_items.append({
            'id': it['id'],
            'name': product_name,
            'quantity': it['qty'],
            'price': it['price'],
            'total': it['qty'] * it['price'],
        })

    currencies = [
        {'code': 'USDT', 'name': 'Tether (USDT)', 'rate': 1, 'icon': 'fab fa-usd'},
        {'code': 'TRX', 'name': 'TRON (TRX)', 'rate': 0.12, 'icon': 'fab fa-tron'},
        {'code': 'BTC', 'name': 'Bitcoin (BTC)', 'rate': 50000, 'icon': 'fab fa-bitcoin'},
        {'code': 'ETH', 'name': 'Ethereum (ETH)', 'rate': 3000, 'icon': 'fab fa-ethereum'},
        {'code': 'BNB', 'name': 'Binance Coin (BNB)', 'rate': 500, 'icon': 'fab fa-bnb'},
        {'code': 'TON', 'name': 'Toncoin (TON)', 'rate': 2.5, 'icon': 'fas fa-coins'}
    ]

    context = {
        'cart_items': cart_items,
        'total_amount': total_amount,
        'currencies': currencies
    }

    return render(request, 'payment.html', context)


def process_payment(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'درخواست نامعتبر'})

    try:
        data = json.loads(request.body.decode('utf-8') if isinstance(request.body, bytes) else request.body)
    except Exception:
        data = {}

    currency = data.get('currency')
    address = data.get('address')
    body_amount = data.get('amount')

    # normalize cart (same logic as checkout)
    raw_cart = request.session.get('cart', [])
    cart_list = []
    if isinstance(raw_cart, dict):
        for item_id, item_data in raw_cart.items():
            cart_list.append({
                'id': str(item_id),
                'qty': int(item_data.get('qty', 1)),
                'price': Decimal(str(item_data.get('price', 0)))
            })
    else:
        for it in raw_cart:
            cart_list.append({
                'id': str(it.get('id')),
                'qty': int(it.get('qty', 1)),
                'price': Decimal(str(it.get('price', 0)))
            })

    if not cart_list:
        return JsonResponse({'success': False, 'message': 'سبد خرید خالی است'})

    total_amount = sum(it['qty'] * it['price'] for it in cart_list)
    # If frontend provided an 'amount', ensure it matches or ignore it
    # Create order
    try:
        order = Order.objects.create(
            user=request.user,
            total_amount=total_amount,
            currency=currency or 'USDT',
            crypto_address=address or '',
            status='PENDING'
        )
        for it in cart_list:
            # try resolve product name
            pname = it['id']
            for group in MEDICINES_DATA.get('medicine_groups', {}).values():
                variants = group.get('variants', {}) or {}
                vlist = variants if isinstance(variants, list) else list(variants.values())
                for variant in vlist:
                    if str(variant.get('id')) == str(it['id']):
                        pname = variant.get('name_fa') or variant.get('name_en') or variant.get('name')
                        break
                if pname != it['id']:
                    break

            OrderItem.objects.create(
                order=order,
                product_id=it['id'],
                name=pname,
                price=it['price'],
                quantity=it['qty']
            )

        # clear cart (keep structure of session consistent)
        request.session['cart'] = []
        request.session.modified = True

        return JsonResponse({'success': True, 'order_id': getattr(order, 'order_id', order.id)})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

def order_success(request):
    return render(request, 'order_success.html')

@login_required
def payment(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    
    # آدرس‌های ثابت
    addresses = {
        'USDT': 'TW88rRvvvoo3dRpippmQJUNmowdmgaCjhE',
        'TRX': 'TW88rRvvvoo3dRpippmQJUNmowdmgaCjhE',
        'BTC': 'bc1qwc2lqwjxwc29tnxn6p2kstsrqcc0ems5957r5m',
        'ETH': '0xaF99374Dd015dA244cdA1F1Fc2183b423a17A10D',
        'BNB': '0xaF99374Dd015dA244cdA1F1Fc2183b423a17A10D',
    }
    
    # محاسبه مبلغ بر اساس نرخ ارز
    rates = get_exchange_rates()  # باید تابع get_exchange_rates را پیاده‌سازی کنید
    amount = order.total_amount / rates[order.currency]['USD']
    
    context = {
        'order': order,
        'address': addresses[order.currency],
        'amount': amount,
        'rates': rates,
    }
    
    return render(request, 'payment.html', context)


def order_history(request):
    return render(request, 'order_history.html')


def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'حساب کاربری شما با موفقیت ایجاد شد!')
            return redirect('home')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
    else:
        form = RegisterForm()
    return render(request, 'register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data['phone']
            password = form.cleaned_data['password']
            # توجه: authenticate ممکن است با username کار کند؛ این پیاده‌سازی برای نمونه است
            user = authenticate(request, username=phone, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, 'خوش آمدید!')
                return redirect('home')
            else:
                messages.error(request, 'شماره تلفن یا رمز عبور اشتباه است')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})


@login_required
def logout_view(request):
    if hasattr(request.user, 'logout_history'):
        logout_history = getattr(request.user, 'logout_history', []) or []
        logout_history.append({
            'logout_time': timezone.now().isoformat(),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')
        })
        request.user.logout_history = logout_history
        request.user.save()

    logout(request)
    messages.success(request, 'با موفقیت خارج شدید.')
    return redirect('home')


@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'پروفایل شما با موفقیت به روز شد!')
            return redirect('profile')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
    else:
        form = ProfileUpdateForm(instance=request.user)
    return render(request, 'profile.html', {'form': form})


def set_language(request):
    if request.method == 'POST':
        language = request.POST.get('lang')
        if language in ['fa', 'en', 'tr', 'ar']:
            request.session['language'] = language
    return redirect(request.META.get('HTTP_REFERER', 'home'))


@login_required
def admin_panel(request):
    if not request.user.is_staff:
        return redirect('home')
    return render(request, 'admin_panel.html')


@login_required
def admin_export_orders_csv(request):
    if not request.user.is_staff:
        return redirect('home')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="orders.csv"'

    writer = csv.writer(response)
    writer.writerow(['Order ID', 'User', 'Amount', 'Currency', 'Status', 'Created At'])

    orders = Order.objects.all()
    for order in orders:
        writer.writerow([getattr(order, 'order_id', ''), getattr(order.user, 'phone', ''), getattr(order, 'amount_usd', ''), getattr(order, 'currency', ''), getattr(order, 'status', ''), getattr(order, 'created_at', '')])

    return response


def api_search(request):
    query = request.GET.get('q', '').strip()
    results = []
    mgroups = MEDICINES_DATA.get('medicine_groups', {})
    for group_key, group_data in mgroups.items():
        variants = group_data.get('variants', []) or []
        vlist = variants if isinstance(variants, list) else list(variants.values())
        for variant in vlist:
            name = variant.get('name', '') or variant.get('name_en', '')
            desc = variant.get('description', '') or variant.get('description_en', '')
            if query.lower() in (name + desc).lower():
                results.append({
                    'id': variant.get('id'),
                    'name': name,
                    'description': desc,
                    'price': variant.get('price'),
                    'group': group_data.get('name', group_key)
                })
    return JsonResponse({'results': results})