from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.utils.translation import gettext_lazy as _
import json
from pathlib import Path
from django.utils import timezone
import uuid
from django.conf import settings
from django.contrib.auth import get_user_model
from decimal import Decimal

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect
from .models import Cart, CartItem

def _get_or_create_cart(request):
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
    else:
        cart_id = request.session.get('cart_id')
        if cart_id:
            try:
                cart = Cart.objects.get(id=cart_id, user__isnull=True)
            except Cart.DoesNotExist:
                cart = Cart.objects.create()
                request.session['cart_id'] = cart.id
        else:
            cart = Cart.objects.create()
            request.session['cart_id'] = cart.id
    return cart

@require_POST
def add_to_cart(request):
    product_id = request.POST.get('product_id')
    name = request.POST.get('name', '')
    price = request.POST.get('price', '0')
    qty = int(request.POST.get('quantity', 1))

    cart = _get_or_create_cart(request)
    item, created = CartItem.objects.get_or_create(cart=cart, product_id=product_id,
                                                   defaults={'name': name, 'price': price, 'quantity': qty})
    if not created:
        item.quantity += qty
        item.save()
    return JsonResponse({'success': True, 'message': 'محصول به سبد اضافه شد', 'cart_count': cart.items.count()})


class CustomUserManager(UserManager):
    def _create_user(self, phone, password, **extra_fields):
        """
        ایجاد کاربر با phone به جای username.
        """
        if not phone:
            raise ValueError('The given phone must be set')
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(phone, password, **extra_fields)

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(phone, password, **extra_fields)

class CustomUser(AbstractUser):
    username = None  # غیرفعال کردن فیلد پیش‌فرض username
    phone = models.CharField(max_length=15, unique=True)
    address = models.TextField(blank=True, null=True)
    language = models.CharField(max_length=5, default='fa')
    logout_history = models.JSONField(default=list, blank=True)

    objects = CustomUserManager()  # استفاده از مدیر جدید

    USERNAME_FIELD = 'phone'  # استفاده از phone برای احراز هویت
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.phone

class Customer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer_profile')
    phone = models.CharField(max_length=32, unique=True)
    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)
    address = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.phone or self.user.username

PAYMENT_CHOICES = [
    ('TRX', 'TRX'),
    ('USDT', 'USDT'),
    ('BTC', 'BTC'),
    ('ETH', 'ETH'),
    ('BNB', 'BNB'),
]

ORDER_STATUS = [
    ('PENDING', 'در انتظار پرداخت'),
    ('PAID', 'پرداخت شده'),
    ('CANCELLED', 'لغو شده'),
]

class Order(models.Model):
    order_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    amount_usd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=8, choices=PAYMENT_CHOICES, default='USDT')
    deposit_address = models.CharField(max_length=256, blank=True)
    status = models.CharField(max_length=16, choices=ORDER_STATUS, default='PENDING')
    created_at = models.DateTimeField(default=timezone.now)
    metadata = models.JSONField(default=dict, blank=True)  # ذخیره سبد یا فیلدهای اضافی

    def __str__(self):
        return f"Order {self.order_id} ({self.user.username})"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def subtotal(self):
        return self.unit_price * self.quantity


# ---------------------------
# Load medicines.json safely
# ---------------------------
MEDICINES_FILE = Path(settings.BASE_DIR) / "medicines.json"

MEDICINES_DATA = {}
TRANSLATIONS = {}

MEDICINE_IMAGES = {}

if MEDICINES_FILE.exists():
    try:
        with open(MEDICINES_FILE, "r", encoding="utf-8") as f:
            DATA = json.load(f)

        # همه گروه‌ها
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

        for key in all_group_keys:
            if key in DATA:
                MEDICINES_DATA[key] = DATA[key]

        TRANSLATIONS = DATA.get("translations", {})
        MEDICINE_IMAGES = DATA.get("medicine_images", {})

        print("✅ Medicines.json loaded groups:", list(MEDICINES_DATA.keys()))
        print("✅ Loaded images:", len(MEDICINE_IMAGES))

    except Exception as e:
        print("❌ Error parsing medicines.json:", e)
else:
    print("⚠️ medicines.json not found at:", MEDICINES_FILE)