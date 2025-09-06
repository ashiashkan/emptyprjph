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
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
import re
from eth_typing import ValidationError
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError


class Cart(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40, null=True, blank=True)  # اضافه
    created = models.DateTimeField(auto_now_add=True)

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product_id = models.CharField(max_length=200)  # یا ForeignKey به مدل محصول شما
    name = models.CharField(max_length=255, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantity = models.PositiveIntegerField(default=1)

class Customer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer_profile')
    phone = models.CharField(max_length=32, unique=True)
    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)
    address = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.phone or self.user.phone

class CustomUserManager(BaseUserManager):
    def _create_user(self, phone, password, **extra_fields):
        if not phone:
            raise ValueError('The given phone must be set')
        
        # اعتبارسنجی شماره تلفن
        if not re.match(r'^\+?1?\d{9,15}$', phone):
            raise ValueError('Phone number must be entered in the format: "+999999999". Up to 15 digits allowed.')
            
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
    username = None
    phone = models.CharField(
        max_length=15, 
        unique=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$','Phone number must be entered in the format: "+999999999". Up to 15 digits allowed.')]
    )
    address = models.TextField(max_length=500, blank=True, null=True)
    language = models.CharField(max_length=5, default='fa')
    logout_history = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.phone

    def clean(self):
        super().clean()
        # اعتبارسنجی شماره تلفن
        if not re.match(r'^\+?1?\d{9,15}$', self.phone):
            raise ValidationError({
                'phone': 'Phone number must be entered in the format: "+999999999". Up to 15 digits allowed.'
            })

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