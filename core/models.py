from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.conf import settings
import json
from pathlib import Path

class CustomUser(AbstractUser):
    phone = models.CharField(max_length=15, unique=True)
    address = models.TextField(blank=True, null=True)
    language = models.CharField(max_length=5, default='fa')
    logout_history = models.JSONField(default=list, blank=True)

    def __str__(self):
        return self.phone or self.username


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    items = models.JSONField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10)
    status = models.CharField(max_length=20, default='PENDING')
    crypto_address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


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
