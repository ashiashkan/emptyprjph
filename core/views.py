from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib import messages
from django.conf import settings
from django.utils.safestring import mark_safe

from .forms import LoginForm, PhoneLoginForm, RegisterForm, AddressForm
from .models import Customer, Order, MEDICINES_DATA, TRANSLATIONS , MEDICINE_IMAGES
import json, time, base64, uuid
from io import BytesIO
import qrcode
from pathlib import Path
from django.contrib.auth.models import User
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages, auth
from django.contrib.auth import authenticate, login, logout
from django.urls import reverse
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.models import User
from decimal import Decimal
import qrcode
import io
import base64
from .models import Customer, Order, OrderItem
from .forms import PhoneLoginForm, RegisterForm, AddressForm
import uuid
from django.views.decorators.http import require_POST


# فایل داروها
MEDICINES_FILE = Path(settings.BASE_DIR) / "medicines.json"
if MEDICINES_FILE.exists():
    with open(MEDICINES_FILE, "r", encoding="utf-8") as f:
        DATA = json.load(f)
else:
    DATA = {}


# دیکشنری تصاویر داروها
MEDICINE_IMAGES = DATA.get("medicine_images", {})

# جمع کردن همه گروه‌ها و variants
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
                vprice = float(v.get("price", 0))
                vimage = MEDICINE_IMAGES.get(vid, None)

                variants.append({
                    "id": vid,
                    "name": vname,
                    "description": vdesc,
                    "price": vprice,
                    "image": vimage,
                })
            groups.append({
                "id": g_name.replace(" ", "_"),
                "name": g_name,
                "variants": variants
            })
    return groups



def buy_medicine(request):
    groups = get_all_groups()

    if request.method == "POST":
        variant_id = request.POST.get("variant_id")
        qty = int(request.POST.get("qty", 1))

        # پیدا کردن محصول انتخابی
        selected_variant = None
        for group in groups:
            for v in group["variants"]:
                if str(v.get("id")) == str(variant_id):
                    selected_variant = v
                    break

        if not selected_variant:
            messages.error(request, "داروی مورد نظر یافت نشد.")
            return redirect("buy_medicine")

        # سبد خرید در session
        cart = request.session.get("cart", [])

        # بررسی اینکه محصول قبلاً توی سبد هست یا نه
        found = False
        for item in cart:
            if item["id"] == variant_id:
                item["qty"] += qty
                found = True
                break

        if not found:
            cart.append({
                "id": variant_id,
                "name": selected_variant["name"],
                "price": float(selected_variant["price"]),
                "qty": qty,
                "image": selected_variant.get("image"),
            })

        # ذخیره در session
        request.session["cart"] = cart
        request.session.modified = True

        messages.success(request, f"{selected_variant['name']} با موفقیت به سبد خرید اضافه شد.")
        return redirect("buy_medicine")

    return render(request, "buy_medicine.html", {"groups": groups})

# --- helpers ---
def generate_deposit_address(currency: str, user_identifier: str):
    """
    Placeholder: تولید یک آدرس یکتا برای پرداخت.
    این تابع را جایگزین کن با تولید آدرس واقعی (web3/tronpy/bitcoinlib) در محیط production.
    """
    return f"{currency}_DEPOSIT_{user_identifier[:8]}_{uuid.uuid4().hex[:12]}"

def create_qr_base64(data: str):
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('ascii')

# --- auth / profile ---
def register_view(request):
    if request.user.is_authenticated:
        return redirect('core:cart')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data['phone'].strip()
            password = form.cleaned_data['password']
            first = form.cleaned_data.get('first_name', '')
            last = form.cleaned_data.get('last_name', '')
            address = form.cleaned_data.get('address', '')

            # create User with username as phone
            if User.objects.filter(username=phone).exists():
                messages.warning(request, "این شماره قبلاً ثبت شده. لطفاً وارد شوید.")
                return redirect('core:login')
            user = User.objects.create_user(username=phone)
            user.set_password(password)
            user.first_name = first
            user.last_name = last
            user.save()

            Customer.objects.create(user=user, phone=phone, first_name=first, last_name=last, address=address)
            login(request, user)
            messages.success(request, "ثبت‌نام با موفقیت انجام شد و وارد شدید.")
            return redirect('core:checkout')
    else:
        form = RegisterForm()
    return render(request, 'core/register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:cart')
    if request.method == 'POST':
        form = PhoneLoginForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data['phone'].strip()
            password = form.cleaned_data['password']
            user = authenticate(request, username=phone, password=password)
            if user:
                login(request, user)
                messages.success(request, "ورود موفق. خوش آمدید.")
                next_url = request.GET.get('next') or reverse('core:checkout')
                return redirect(next_url)
            else:
                messages.error(request, "شماره یا رمز اشتباه است.")
    else:
        form = PhoneLoginForm()
    return render(request, 'core/login.html', {'form': form})

def profile_view(request):
    if not request.user.is_authenticated:
        return redirect('core:login')
    customer, _ = Customer.objects.get_or_create(user=request.user, phone=request.user.username)
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            customer.first_name = form.cleaned_data.get('first_name', '')
            customer.last_name = form.cleaned_data.get('last_name', '')
            customer.address = form.cleaned_data.get('address', '')
            customer.save()
            messages.success(request, "اطلاعات ویرایش شد.")
            return redirect('core:profile')
    else:
        form = AddressForm(initial={'first_name': customer.first_name, 'last_name': customer.last_name, 'address': customer.address})
    return render(request, 'core/profile.html', {'form': form, 'customer': customer})

def logout_view(request):
    auth.logout(request)
    messages.success(request, "شما خارج شدید.")
    return redirect('core:login')

# --- cart / checkout ---
def cart_view(request):
    # سبد در session نگهداری شده: session['cart'] = [{'name':..., 'price': '12.50', 'qty': 2}, ...]
    cart = request.session.get('cart', [])
    total = sum(Decimal(item['price']) * int(item.get('qty', 1)) for item in cart) if cart else Decimal('0.00')
    return render(request, 'core/cart.html', {'cart': cart, 'total': total})

def add_to_cart_view(request):
    # نمونه endpoint برای افزودن (اگر لازم باشه)
    if request.method != 'POST':
        return HttpResponseForbidden()
    name = request.POST.get('name')
    price = request.POST.get('price', '0')
    qty = int(request.POST.get('qty', 1))
    cart = request.session.get('cart', [])
    cart.append({'name': name, 'price': str(price), 'qty': qty})
    request.session['cart'] = cart
    return JsonResponse({'ok': True, 'cart_count': len(cart)})

def checkout_view(request):
    # اگر کاربر لاگین نیست: redirect به صفحه لاگین با next
    if not request.user.is_authenticated:
        return redirect(f"{reverse('core:login')}?next={reverse('core:checkout')}")
    # اطمینان از داشتن آدرس کاربر
    customer, _ = Customer.objects.get_or_create(user=request.user, phone=request.user.username)
    cart = request.session.get('cart', [])
    if not cart:
        messages.info(request, "سبد شما خالی است.")
        return redirect('core:cart')
    # اگر آدرس خالی هست، هدایت به صفحه پروفایل برای تکمیل
    if not customer.address:
        messages.warning(request, "قبل از پرداخت، لطفاً آدرس و اطلاعات خود را تکمیل کنید.")
        return redirect('core:profile')

    total_usd = sum(Decimal(item['price']) * int(item.get('qty', 1)) for item in cart)
    if request.method == 'POST':
        currency = request.POST.get('currency', 'USDT')  # انتخاب کاربر
        # ایجاد سفارش
        order = Order.objects.create(user=request.user, amount_usd=total_usd, currency=currency, metadata={'cart_snapshot': cart})
        # تولید آدرس پرداخت
        deposit_address = generate_deposit_address(currency, str(order.order_id))
        order.deposit_address = deposit_address
        order.save()
        # ایجاد آیتم‌ها
        for it in cart:
            OrderItem.objects.create(order=order, name=it['name'], unit_price=Decimal(it['price']), quantity=int(it.get('qty', 1)))
        # پاک کردن سبد session (یا نگه‌داشتن در صورت نیاز)
        # request.session['cart'] = []
        return redirect('core:payment', order_id=order.order_id)

    # نمایش فرم انتخاب ارز و خلاصه فاکتور
    return render(request, 'core/checkout.html', {'customer': customer, 'cart': cart, 'total': total_usd, 'payment_options': ['TRX','USDT','BTC','ETH','BNB']})

def payment_view(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    items = order.items.all()
    qr_b64 = create_qr_base64(order.deposit_address)
    return render(request, 'core/payment.html', {'order': order, 'items': items, 'qr_b64': qr_b64})

@require_POST
def check_payment_ajax(request, order_id):
    """
    نمونه ساده: در اینجا فقط وضعیت را از فیلد order.status می‌خوانیم.
    در محیط واقعی باید با بلاکچین/اپی‌ها بررسی شود و پس از تایید، وضعیت order را به PAID تغییر دهیم.
    """
    order = get_object_or_404(Order, order_id=order_id)
    # TODO: call real check_payment(order.deposit_address, order.currency, order.amount_usd)
    if order.status == 'PAID':
        return JsonResponse({'paid': True})
    else:
        # برای نمونه: برگشت وضعیت pending
        return JsonResponse({'paid': False, 'status': order.status})



# ---------- i18n helpers ----------
FALLBACK_TEXTS = {
    'fa': {
        'home': 'خانه',
        'login': 'ورود',
        'register': 'ثبت‌نام',
        'logout_success': 'با موفقیت خارج شدید.',
        'logout_blocked': 'لطفاً {minutes} دقیقه دیگر دوباره تلاش کنید.',
        'invalid_credentials': 'شماره یا رمز عبور نادرست است.',
        'cart_empty': 'سبد خرید شما خالی است.',
        'register_first': 'برای نهایی کردن خرید، ابتدا آدرس خود را در پروفایل ثبت کنید.',
        'payment_success': 'سفارش شما ثبت شد. پس از بررسی پرداخت، با شما تماس می‌گیریم.',
        'order_history': 'سوابق سفارش',
        'guide': 'راهنمای خرید',
        'support': 'پشتیبانی',
        'profile': 'پروفایل',
        'change_language': 'تغییر زبان',
    },
    'en': {
        'logout_success': 'Logged out successfully.',
        'logout_blocked': 'Please try again in {minutes} minutes.',
        'invalid_credentials': 'Invalid phone or password.',
        'cart_empty': 'Your cart is empty.',
        'register_first': 'Please fill your address in profile before checkout.',
        'payment_success': 'Your order was created. We will confirm after payment verification.',
    }
}

def get_text(lang, key, **kwargs):
    txt = TRANSLATIONS.get(lang, {}).get(key) or TRANSLATIONS.get('en', {}).get(key) or FALLBACK_TEXTS.get(lang, {}).get(key) or FALLBACK_TEXTS.get('en', {}).get(key) or key
    if kwargs:
        try:
            return txt.format(**kwargs)
        except Exception:
            return txt
    return txt

# simple anti-spam logout: block repeated logout within 1 minute
def check_logout_spam(user):
    hist = getattr(user, 'logout_history', []) or []
    now = time.time()
    hist = [t for t in hist if now - t < 60]  # keep last 60s
    allowed = (len(hist) == 0 or now - hist[-1] > 10)
    remaining = max(0, 60 - int(now - (hist[-1] if hist else 0)))
    return allowed, remaining

# ---------- Views ----------
class HomeView(View):
    def get(self, request):
        lang = request.session.get('language', 'fa')
        groups = []
        for gkey, group in (MEDICINES_DATA or {}).items():
            name = group.get(f'name_{lang}') or group.get('name_en') or gkey
            variants = []
            for vid, v in (group.get('variants') or group.get('rogams') or {}).items():
                vname = v.get(f'name_{lang}') or v.get('name_en') or vid
                vdesc = v.get(f'description_{lang}') or v.get('description_en') or ''
                price = float(v.get('price', 0))
                variants.append({'id': vid, 'name': vname, 'description': vdesc, 'price': price})
            groups.append({'id': gkey, 'name': name, 'variants': variants})
        cart_count = len(request.session.get('cart', []))
        return render(request, 'home.html', {
            'groups': groups,
            'lang': lang,
            'cart_count': cart_count
        })

    def post(self, request):
        cart = request.session.get('cart', [])
        variant_id = request.POST.get('variant_id')
        qty = int(request.POST.get('qty', 1) or 1)
        # جستجو در دیتای دارو
        for group in (MEDICINES_DATA or {}).values():
            variants = group.get('variants') or group.get('rogams') or {}
            if variant_id in variants:
                v = variants[variant_id]
                cart.append({
                    'id': variant_id,
                    'name': v.get('name_en') or variant_id,
                    'price': float(v.get('price', 0)),
                    'qty': qty
                })
                request.session['cart'] = cart
                messages.success(request, "به سبد خرید اضافه شد ✅")
                break
        return redirect('home')


class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('home')
        return render(request, 'login.html', {'form': LoginForm()})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data['phone']
            password = form.cleaned_data['password']
            user = authenticate(request, username=phone, password=password)
            if user:
                login(request, user)
                request.session['language'] = getattr(user, 'language', 'fa')
                return redirect('home')
            messages.error(request, get_text(request.session.get('language','fa'), 'invalid_credentials'))
        return render(request, 'login.html', {'form': form})

class RegisterView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('home')
        return render(request, 'register.html', {'form': RegisterForm()})

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            # username = phone for login
            user.username = form.cleaned_data['phone']
            user.set_password(form.cleaned_data['password'])
            user.save()
            login(request, user)
            request.session['language'] = getattr(user, 'language', 'fa')
            return redirect('home')
        return render(request, 'register.html', {'form': form})

class LogoutView(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return redirect('login')
        allowed, remaining = check_logout_spam(request.user)
        if allowed:
            # store in user profile
            hist = request.user.logout_history or []
            hist.append(time.time())
            request.user.logout_history = hist
            request.user.save(update_fields=['logout_history'])
            logout(request)
            messages.success(request, get_text(request.session.get('language','fa'), 'logout_success'))
        else:
            messages.error(request, get_text(request.session.get('language','fa'), 'logout_blocked', minutes=remaining))
        return redirect('home')


class BuyMedicineView(View):
    def get(self, request):
        lang = request.session.get('language', 'fa')
        groups = []

        all_group_keys = [
            "medicine_groups", "faroxy_groups", "tramadol_groups",
            "methadone_groups", "methylphenidate_groups", "phyto_groups",
            "seretide_groups", "modafinil_groups", "monjaro_groups",
            "insuline_groups", "soma_groups", "biobepa_groups",
            "warfarine_groups", "gardasil_groups", "rogam_groups",
            "Aminoven_groups", "Nexium_groups", "Exelon_groups",
            "testestron_groups", "zithromax_groups", "Liskantin_groups",
            "chimi_groups"
        ]

        for group_key in all_group_keys:
            group_dict = MEDICINES_DATA.get(group_key, {})
            for gkey, group in group_dict.items():
                name = group.get(f'name_{lang}') or group.get('name_en') or gkey

                variant_dict = None
                for k, v in group.items():
                    if isinstance(v, dict):
                        variant_dict = v
                        break

                variants = []
                if variant_dict:
                    for vid, v in variant_dict.items():
                        vname = v.get(f'name_{lang}') or v.get('name_en') or vid
                        vdesc = v.get(f'description_{lang}') or v.get('description_en') or ''
                        price = float(v.get('price', 0))

                        img_path = MEDICINE_IMAGES.get(vid, "")
                        if img_path:
                            img_url = settings.STATIC_URL + img_path
                        else:
                            img_url = settings.STATIC_URL + "images/default.jpg"

                        variants.append({
                            'id': vid,
                            'name': vname,
                            'description': vdesc,
                            'price': price,
                            'image': img_url,
                        })

                groups.append({
                    'id': f"{group_key}_{gkey}",
                    'name': name,
                    'variants': variants
                })

        return render(request, 'buy_medicine.html', {
            'groups': groups,
            'messages': messages.get_messages(request)  # اضافه کردن پیام‌ها به context
        })

    def post(self, request):
        variant_id = request.POST.get("variant_id")
        qty = int(request.POST.get("qty", 1))
        
        # پیدا کردن محصول انتخابی
        selected_variant = None
        all_group_keys = [
            "medicine_groups", "faroxy_groups", "tramadol_groups",
            "methadone_groups", "methylphenidate_groups", "phyto_groups",
            "seretide_groups", "modafinil_groups", "monjaro_groups",
            "insuline_groups", "soma_groups", "biobepa_groups",
            "warfarine_groups", "gardasil_groups", "rogam_groups",
            "Aminoven_groups", "Nexium_groups", "Exelon_groups",
            "testestron_groups", "zithromax_groups", "Liskantin_groups",
            "chimi_groups"
        ]

        for group_key in all_group_keys:
            group_dict = MEDICINES_DATA.get(group_key, {})
            for gkey, group in group_dict.items():
                variant_dict = None
                for k, v in group.items():
                    if isinstance(v, dict):
                        variant_dict = v
                        break
                
                if variant_dict and variant_id in variant_dict:
                    v = variant_dict[variant_id]
                    lang = request.session.get('language', 'fa')
                    vname = v.get(f'name_{lang}') or v.get('name_en') or variant_id
                    selected_variant = {
                        'id': variant_id,
                        'name': vname,
                        'price': float(v.get('price', 0)),
                        'image': MEDICINE_IMAGES.get(variant_id, "")
                    }
                    break
            if selected_variant:
                break

        if not selected_variant:
            messages.error(request, "داروی مورد نظر یافت نشد.")
            return redirect("buy_medicine")

        # سبد خرید در session
        cart = request.session.get("cart", [])
        
        # بررسی اینکه محصول قبلاً توی سبد هست یا نه
        found = False
        for item in cart:
            if item["id"] == variant_id:
                item["qty"] += qty
                found = True
                break

        if not found:
            cart.append({
                "id": variant_id,
                "name": selected_variant["name"],
                "price": float(selected_variant["price"]),
                "qty": qty,
                "image": selected_variant.get("image"),
            })

        # ذخیره در session
        request.session["cart"] = cart
        request.session.modified = True

        messages.success(request, f"{selected_variant['name']} با موفقیت به سبد خرید اضافه شد.")
        return redirect("buy_medicine")


class CartView(View):
    def get(self, request):
        lang = request.session.get('language', 'fa')
        cart = request.session.get('cart', [])
        total = sum(float(i.get('price',0))*int(i.get('qty',1)) for i in cart)
        return render(request, 'cart.html', {'cart': cart, 'total': total, 'lang': lang})

    def post(self, request):
        action = request.POST.get('action')
        cart = request.session.get('cart', [])
        
        if action == 'remove':
            idx = int(request.POST.get('index', -1))
            if 0 <= idx < len(cart):
                del cart[idx]
                messages.success(request, "محصول از سبد خرید حذف شد.")
                
        elif action == 'update':
            idx = int(request.POST.get('index', -1))
            qty = int(request.POST.get('qty', 1))
            if 0 <= idx < len(cart) and qty > 0:
                cart[idx]['qty'] = qty
                messages.success(request, "تعداد محصول به‌روزرسانی شد.")
                
        elif action == 'checkout':
            if not request.user.is_authenticated:
                messages.warning(request, 'ابتدا وارد شوید')
                return redirect('login')
            if not getattr(request.user, 'address', None):
                messages.warning(request, get_text(request.session.get('language','fa'), 'register_first'))
                return redirect('profile')
            return redirect('payment')
            
        request.session['cart'] = cart
        request.session.modified = True
        return redirect('cart')


class PaymentView(View):
    @method_decorator(login_required)
    def get(self, request):
        cart = request.session.get('cart', [])
        if not cart:
            return redirect('cart')
        total = sum(float(i.get('price',0))*int(i.get('qty',1)) for i in cart)
        addresses = {
            'BTC': getattr(settings, 'BITCOIN_MAIN_WALLET', 'N/A'),
            'ETH': getattr(settings, 'ETHEREUM_MAIN_WALLET', 'N/A'),
            'TRX': getattr(settings, 'TRON_MAIN_WALLET', 'N/A'),
        }
        qr_codes = {}
        for k, addr in addresses.items():
            img = qrcode.make(addr)
            buf = BytesIO()
            img.save(buf, format='PNG')
            qr_codes[k] = base64.b64encode(buf.getvalue()).decode('ascii')
        return render(request, 'payment.html', {'total': total, 'addresses': addresses, 'qr_codes': qr_codes})

    @method_decorator(login_required)
    def post(self, request):
        currency = request.POST.get('currency', 'BTC')
        cart = request.session.get('cart', [])
        if not cart:
            return redirect('cart')
        total = sum(float(i.get('price',0))*int(i.get('qty',1)) for i in cart)
        address_map = {
            'BTC': getattr(settings, 'BITCOIN_MAIN_WALLET', 'N/A'),
            'ETH': getattr(settings, 'ETHEREUM_MAIN_WALLET', 'N/A'),
            'TRX': getattr(settings, 'TRON_MAIN_WALLET', 'N/A'),
        }
        order = Order.objects.create(
            user=request.user,
            items=cart,
            total_amount=total,
            currency=currency,
            status='PENDING',
            crypto_address=address_map.get(currency,'N/A')
        )
        # clear cart
        request.session['cart'] = []
        messages.success(request, get_text(request.session.get('language','fa'), 'payment_success'))
        return redirect('order_history')

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
            messages.success(request, 'ذخیره شد')
            return redirect('profile')
        return render(request, 'profile.html', {'form': form})

class OrderHistoryView(View):
    @method_decorator(login_required)
    def get(self, request):
        orders = Order.objects.filter(user=request.user).order_by('-created_at')
        return render(request, 'order_history.html', {'orders': orders})

class AdminPanelView(View):
    @method_decorator(login_required)
    def get(self, request):
        if not request.user.is_superuser:
            return redirect('home')
        orders = Order.objects.all().order_by('-created_at')
        return render(request, 'admin_panel.html', {'orders': orders})

class GuideView(View):
    def get(self, request):
        return render(request, 'guide.html')

class SupportView(View):
    def get(self, request):
        return render(request, 'support.html')

class ChangeLanguageView(View):
    def post(self, request):
        lang = request.POST.get('lang', 'fa')
        request.session['language'] = lang
        if request.user.is_authenticated:
            request.user.language = lang
            request.user.save(update_fields=['language'])
        return redirect('home')
