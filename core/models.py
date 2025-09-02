from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
import json
from pathlib import Path
from django.utils import timezone
import uuid
from django.conf import settings
from django.contrib.auth import get_user_model
from decimal import Decimal


class CustomUser(AbstractUser):
    username = None  # غیرفعال کردن فیلد پیش‌فرض username
    phone = models.CharField(max_length=15, unique=True)
    address = models.TextField(blank=True, null=True)
    language = models.CharField(max_length=5, default='fa')
    logout_history = models.JSONField(default=list, blank=True)

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
