from __future__ import annotations

import json
import os
import csv
import io
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple, Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordChangeForm
from django.core.paginator import Paginator
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.utils.translation import gettext_lazy as _

from .forms import LoginForm, RegisterForm, AddressForm
from .models import CustomUser, Order, OrderItem, MEDICINES_DATA, TRANSLATIONS, MEDICINE_IMAGES

import re
from django.views.decorators.http import require_http_methods
# =====================================================
# Constants & Keys
# =====================================================

LANG_FALLBACKS = ["en", "fa", "tr", "ar"]  # Priority: en > fa > tr > ar
CART_KEY = "cart"
ORDERS_KEY = "orders"
LANG_KEY = "language"

ALL_GROUP_KEYS = [
    "medicine_groups", "faroxy_groups", "tramadol_groups",
    "methadone_groups", "methylphenidate_groups", "phyto_groups",
    "seretide_groups", "modafinil_groups", "monjaro_groups",
    "insuline_groups", "soma_groups", "biobepa_groups",
    "warfarine_groups", "gardasil_groups", "rogam_groups",
    "Aminoven_groups", "Nexium_groups", "Exelon_groups",
    "testestron_groups", "zithromax_groups", "Liskantin_groups",
    "chimi_groups"
]

# =====================================================
# Helper structures
# =====================================================

@dataclass
class LocalizedItem:
    id: str
    group_key: str
    name: str
    price: float
    description: str
    exp: str
    image: Optional[str] = None

@dataclass
class LocalizedGroup:
    key: str
    name: str
    variants: List[LocalizedItem] = field(default_factory=list)

# =====================================================
# JSON loader & i18n from medicines.json
# =====================================================

# ——— کَش و منابع:
_JSON_CACHE: Dict[str, Any] = {}
_ITEMS_RAW: Dict[str, Dict[str, Any]] = {}
_GROUPS_RAW: Dict[str, Dict[str, Any]] = {}
_IMAGES_MAP: Dict[str, str] = {}
_TRANSLATIONS: Dict[str, Dict[str, str]] = {}


def _json_path() -> str:
    return os.path.join(settings.BASE_DIR, "medicines.json")


def _pick_name(d: Dict[str, Any]) -> Optional[str]:
    for lang in LANG_FALLBACKS:
        val = d.get(f"name_{lang}")
        if val:
            return val
    return d.get("name") or None

def _pick_desc(d: Dict[str, Any], lang: str) -> str:
    # description_{lang} -> desc_{lang} -> about_{lang}
    for key_base in ("description", "desc", "about"):
        val = d.get(f"{key_base}_{lang}")
        if val:
            return val
        for fb in LANG_FALLBACKS:
            val = d.get(f"{key_base}_{fb}")
            if val:
                return val
    return d.get("description") or ""

def _parse_price(v: Any) -> float:
    # price | price_usd | usd | Price ... (اولین عدد)
    cands = [ "price", "price_usd", "usd", "Price", "PRICE" ]
    raw = None
    for k in cands:
        if isinstance(v, dict) and k in v:
            raw = v[k]
            break
        if not isinstance(v, dict) and k == "price":
            raw = v
            break
    if raw is None:
        return 0.0
    # استخراج عدد
    tokens = re.findall(r"[\d.]+", str(raw))
    return float(tokens[0]) if tokens else 0.0

def _is_item_dict(d: Dict[str, Any]) -> bool:
    if not isinstance(d, dict):
        return False
    if "price" in d or "price_usd" in d or "usd" in d or "Price" in d or "PRICE" in d:
        return True
    return False

def _ensure_loaded() -> None:
    """
    منبع داده را از models.MEDICINES_DATA (اگر از قبل لود شده) یا مستقیم از فایل می‌گیریم،
    سپس به‌صورت بازگشتی تمام آیتم‌ها را در هر عمقی استخراج می‌کنیم.
    """
    global _JSON_CACHE, _ITEMS_RAW, _GROUPS_RAW, _IMAGES_MAP, _TRANSLATIONS

    if _ITEMS_RAW and _GROUPS_RAW:
        return

    # منبع اولیه از models.py اگر موجود باشد
    source_groups: Dict[str, Any] = {}
    if MEDICINES_DATA:
        source_groups = MEDICINES_DATA
        _IMAGES_MAP = MEDICINE_IMAGES or {}
        _TRANSLATIONS = TRANSLATIONS or {}

    # در غیر این‌صورت از فایل
    if not source_groups:
        path = _json_path()
        if not os.path.exists(path):
            raise FileNotFoundError(f"medicines.json not found at {path}")
        with open(path, "r", encoding="utf-8") as f:
            _JSON_CACHE = json.load(f)
        _IMAGES_MAP = _JSON_CACHE.get("medicine_images", {})
        _TRANSLATIONS = _JSON_CACHE.get("translations", {})
        source_groups = {k: _JSON_CACHE.get(k, {}) for k in ALL_GROUP_KEYS if isinstance(_JSON_CACHE.get(k), dict)}

    _ITEMS_RAW.clear()
    _GROUPS_RAW.clear()

    def collect_items_under(group_key: str, node: Dict[str, Any]):
        """هر آیتمی که price دارد را (در هر عمقی) ثبت می‌کند."""
        if not isinstance(node, dict):
            return
        # اگر این نود خودش آیتم است
        if _is_item_dict(node):
            # شناسه: اگر در داده‌ها id جدا نداریم، کلید والد باید item_id باشد؛
            # این تابع با کلیدهای خارجی فراخوانی می‌شود، پس اینجا فقط رد می‌شویم.
            return

        for k, v in node.items():
            if isinstance(v, dict):
                if _is_item_dict(v):
                    _ITEMS_RAW[k] = {**v, "group_key": group_key}
                else:
                    collect_items_under(group_key, v)

    # روی تمام گروه‌های سطح بالا → زیربخش‌ها
    for top_key, container in source_groups.items():
        if not isinstance(container, dict):
            continue
        for subgroup_key, subgroup in container.items():
            if not isinstance(subgroup, dict):
                continue
            # مشخصات گروه
            gname = _pick_name(subgroup) or subgroup_key
            _GROUPS_RAW[subgroup_key] = {"name": gname, "raw": subgroup}
            # جمع‌آوری آیتم‌ها (از variants یا هر عمق)
            if isinstance(subgroup.get("variants"), dict):
                for vid, vraw in subgroup["variants"].items():
                    if isinstance(vraw, dict) and _is_item_dict(vraw):
                        _ITEMS_RAW[vid] = {**vraw, "group_key": subgroup_key}
                    else:
                        collect_items_under(subgroup_key, vraw)
            else:
                collect_items_under(subgroup_key, subgroup)

    print(f"✅ Loaded {len(_GROUPS_RAW)} groups, {len(_ITEMS_RAW)} items, {len(_IMAGES_MAP)} images")

def localize_item(item_id: str, lang: str) -> Optional[LocalizedItem]:
    raw = _ITEMS_RAW.get(item_id)
    if not raw:
        return None
    group_key = raw.get("group_key", "unknown")
    name = raw.get(f"name_{lang}") or _pick_name(raw) or item_id
    desc = _pick_desc(raw, lang)
    price = _parse_price(raw)
    exp = raw.get("exp") or raw.get("expire") or raw.get("expiry") or ""
    image = _IMAGES_MAP.get(item_id) or raw.get("image")

    return LocalizedItem(
        id=item_id,
        group_key=group_key,
        name=name,
        price=price,
        description=desc,
        exp=exp,
        image=image,
    )

def localize_group(group_key: str, lang: str) -> Optional[LocalizedGroup]:
    graw = _GROUPS_RAW.get(group_key)
    if not graw:
        return None
    # نام گروه با ترجمه داخل خود گروه
    name = graw["raw"].get(f"name_{lang}") or _pick_name(graw["raw"]) or group_key
    variants: List[LocalizedItem] = []
    for vid, v in _ITEMS_RAW.items():
        if v.get("group_key") == group_key:
            li = localize_item(vid, lang)
            if li:
                variants.append(li)
    # مرتب‌سازی: اول بر اساس نام، سپس قیمت
    variants.sort(key=lambda x: (x.name.lower(), x.price))
    return LocalizedGroup(key=group_key, id=group_key, name=name, variants=variants)

def get_translation(key: str, lang: str) -> str:
    return _TRANSLATIONS.get(key, {}).get(lang, key)

# =====================================================
# Language helpers
# =====================================================

def get_lang(request: HttpRequest) -> str:
    return request.session.get(LANG_KEY, request.user.language if request.user.is_authenticated else 'fa')

def set_lang(request: HttpRequest, code: str) -> None:
    if code in ['fa', 'en', 'tr', 'ar']:
        request.session[LANG_KEY] = code
        if request.user.is_authenticated:
            request.user.language = code
            request.user.save()

@require_POST
def set_language(request: HttpRequest) -> HttpResponse:
    code = request.POST.get("language")
    if code:
        set_lang(request, code)
    return redirect(request.META.get("HTTP_REFERER", "/"))

# =====================================================
# Views: Home, Guide, Support
# =====================================================

@require_GET
def home(request: HttpRequest) -> HttpResponse:
    _ensure_loaded()
    lang = get_lang(request)
    context = {
        "title": get_translation("welcome", lang),
        "lang": lang,
    }
    return render(request, "home.html", context)

@require_GET
def guide(request: HttpRequest) -> HttpResponse:
    _ensure_loaded()
    lang = get_lang(request)
    context = {
        "title": get_translation("guide", lang),
        "lang": lang,
    }
    return render(request, "guide.html", context)

@require_GET
def support(request: HttpRequest) -> HttpResponse:
    _ensure_loaded()
    lang = get_lang(request)
    context = {
        "title": get_translation("support", lang),
        "lang": lang,
    }
    return render(request, "support.html", context)

# =====================================================
# Views: Medicines List & Detail
# =====================================================

@require_http_methods(["GET", "POST"])
def buy_medicine(request: HttpRequest) -> HttpResponse:
    _ensure_loaded()
    lang = get_lang(request)

    # افزودن به سبد از همان صفحه
    if request.method == "POST":
        item_id = request.POST.get("variant_id")
        qty = int(request.POST.get("qty", 1) or 1)
        if not item_id or item_id not in _ITEMS_RAW:
            messages.error(request, "آیتم نامعتبر است.")
            return redirect("buy_medicine")
        if not request.user.is_authenticated:
            messages.info(request, "برای افزودن به سبد ابتدا وارد شوید.")
            return redirect("login")
        cart = request.session.get(CART_KEY, {})
        cart[item_id] = cart.get(item_id, 0) + max(1, qty)
        request.session[CART_KEY] = cart
        messages.success(request, "به سبد خرید افزوده شد.")
        return redirect("buy_medicine")

    query = request.GET.get("q", "").strip().lower()

    groups: List[LocalizedGroup] = []
    for gkey in _GROUPS_RAW.keys():
        loc_group = localize_group(gkey, lang)
        if not loc_group:
            continue
        if query:
            filtered = [
                v for v in loc_group.variants
                if (query in v.name.lower() or query in v.description.lower() or query in v.id.lower())
            ]
            if not filtered:
                continue
            loc_group.variants = filtered
        # فقط گروه‌هایی که آیتم دارند
        if loc_group.variants:
            groups.append(loc_group)

    # مرتب‌سازی گروه‌ها بر اساس نام
    groups.sort(key=lambda g: g.name)

    paginator = Paginator(groups, 4)  # ۴ گروه در هر صفحه
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "groups": page_obj,
        "query": query,
        "title": get_translation("pharmacy_online", lang),
        "lang": lang,
        "page_obj": page_obj,
    }
    return render(request, "buy_medicine.html", context)


@require_GET
def medicine_detail(request: HttpRequest, item_id: str) -> HttpResponse:
    _ensure_loaded()
    lang = get_lang(request)
    item = localize_item(item_id, lang)
    if not item:
        return HttpResponseBadRequest("Item not found")

    context = {
        "item": item,
        "title": item.name,
        "lang": lang,
    }
    return render(request, "medicine_detail.html", context)  # Create if missing: detail view with image, desc, price, exp, add to cart button

# =====================================================
# Cart Views
# =====================================================

def get_cart(request: HttpRequest) -> Dict[str, Dict]:
    return request.session.get(CART_KEY, {})

def save_cart(request: HttpRequest, cart: Dict[str, Dict]) -> None:
    request.session[CART_KEY] = cart

@require_GET
@login_required
def cart_view(request: HttpRequest) -> HttpResponse:
    _ensure_loaded()
    lang = get_lang(request)
    cart = get_cart(request)
    items = []
    total = 0.0
    for item_id, qty in cart.items():
        item = localize_item(item_id, lang)
        if item:
            subtotal = item.price * qty
            total += subtotal
            items.append({
                "item": item,
                "qty": qty,
                "subtotal": subtotal,
            })

    context = {
        "items": items,
        "total": total,
        "title": get_translation("cart", lang),
        "lang": lang,
    }
    return render(request, "cart.html", context)

@require_POST
@login_required
def cart_add(request: HttpRequest, item_id: str) -> HttpResponse:
    _ensure_loaded()
    if item_id not in _ITEMS_RAW:
        return HttpResponseBadRequest("Invalid item")

    cart = get_cart(request)
    qty = int(request.POST.get("qty", 1))
    cart[item_id] = cart.get(item_id, 0) + qty
    save_cart(request, cart)
    messages.success(request, "Item added to cart")
    return redirect("cart")

@require_POST
@login_required
def cart_update(request: HttpRequest, item_id: str) -> HttpResponse:
    cart = get_cart(request)
    action = request.POST.get("action")
    if action == "remove":
        cart.pop(item_id, None)
    elif action == "update":
        qty = int(request.POST.get("qty", 1))
        if qty > 0:
            cart[item_id] = qty
        else:
            cart.pop(item_id, None)
    save_cart(request, cart)
    return redirect("cart")

# =====================================================
# Checkout & Orders
# =====================================================

@login_required
@require_POST
def checkout(request: HttpRequest) -> HttpResponse:
    _ensure_loaded()
    lang = get_lang(request)
    cart = get_cart(request)
    if not cart:
        return redirect("cart")

    items = []
    total_usd = 0.0
    for item_id, qty in cart.items():
        item = localize_item(item_id, lang)
        if item:
            subtotal = item.price * qty
            total_usd += subtotal
            items.append({
                "name": item.name,
                "unit_price": item.price,
                "quantity": qty,
            })

    currency = request.POST.get("currency", "USDT")
    order = Order.objects.create(
        user=request.user,
        amount_usd=total_usd,
        currency=currency,
        deposit_address="demo_address_" + currency,  # Replace with real wallet logic
        metadata={"items": items},
    )

    for it in items:
        OrderItem.objects.create(
            order=order,
            name=it["name"],
            unit_price=it["unit_price"],
            quantity=it["quantity"],
        )

    # Clear cart
    save_cart(request, {})

    # Save to session for admin (demo)
    session_orders = request.session.get(ORDERS_KEY, [])
    session_orders.append({
        "id": str(order.order_id),
        "user": request.user.phone,
        "created": timezone.now().isoformat(),
        "status": order.status,
        "total": total_usd,
        "items": items,
    })
    request.session[ORDERS_KEY] = session_orders

    return redirect("payment", order_id=order.order_id)  # Add payment.html or adjust

# Add payment view if missing
@require_GET
@login_required
def payment(request: HttpRequest, order_id: str) -> HttpResponse:
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    context = {
        "order": order,
        "items": order.items.all(),
        "title": "Payment",
    }
    return render(request, "payment.html", context)

@require_GET
@login_required
def order_history(request: HttpRequest) -> HttpResponse:
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    context = {
        "orders": orders,
        "title": "Order History",
    }
    return render(request, "order_history.html", context)

# =====================================================
# Auth Views
# =====================================================

@require_GET
def login_view(request: HttpRequest) -> HttpResponse:
    form = LoginForm()
    return render(request, "login.html", {"form": form})

@require_POST
def login_submit(request: HttpRequest) -> HttpResponse:
    form = LoginForm(request.POST)
    if form.is_valid():
        phone = form.cleaned_data["phone"]
        password = form.cleaned_data["password"]
        user = authenticate(request, phone=phone, password=password)
        if user:
            login(request, user)
            set_lang(request, user.language)
            return redirect("home")
    messages.error(request, "Invalid credentials")
    return redirect("login")

@require_GET
def register_view(request: HttpRequest) -> HttpResponse:
    form = RegisterForm()
    return render(request, "register.html", {"form": form})

@require_POST
def register_submit(request: HttpRequest) -> HttpResponse:
    form = RegisterForm(request.POST)
    if form.is_valid():
        user = form.save()
        login(request, user)
        set_lang(request, user.language)
        return redirect("home")
    return render(request, "register.html", {"form": form})

@require_POST
@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("home")

@require_GET
@login_required
def profile(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = AddressForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated")
    else:
        form = AddressForm(instance=request.user)
    context = {
        "form": form,
        "title": "Profile",
    }
    return render(request, "profile.html", context)

# =====================================================
# Admin Views
# =====================================================

def staff_required(view_func):
    return user_passes_test(lambda u: u.is_staff)(view_func)

@staff_required
@require_GET
def admin_panel(request: HttpRequest) -> HttpResponse:
    orders = Order.objects.all().order_by("-created_at")
    total = sum(o.amount_usd for o in orders)
    context = {
        "orders": orders,
        "count": orders.count(),
        "sum_total": total,
        "title": "Admin Panel",
    }
    return render(request, "admin_panel.html", context)

@staff_required
@require_POST
def admin_export_orders_csv(request: HttpRequest) -> HttpResponse:
    orders = Order.objects.all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["OrderID", "User", "Created", "Status", "Total USD", "Currency", "Items"])
    for o in orders:
        items_str = "; ".join(f"{i.name} x{i.quantity} @ {i.unit_price}" for i in o.items.all())
        writer.writerow([o.order_id, o.user.phone, o.created_at, o.status, o.amount_usd, o.currency, items_str])
    response = HttpResponse(output.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=orders.csv"
    return response

# =====================================================
# API: Search
# =====================================================

@require_GET
def api_search(request: HttpRequest) -> JsonResponse:
    _ensure_loaded()
    lang = get_lang(request)
    q = request.GET.get("q", "").strip().lower()
    if not q:
        return JsonResponse({"results": []})
    results = []
    for item_id in _ITEMS_RAW:
        item = localize_item(item_id, lang)
        if item and (q in item.name.lower() or q in item.description.lower() or q in item_id.lower()):
            results.append(asdict(item))
            if len(results) >= 30:
                break
    return JsonResponse({"results": results})