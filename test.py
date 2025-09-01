from django.shortcuts import render, redirect
from django.views import View
from django.conf import settings
import json
from pathlib import Path

# 📦 بارگذاری داده‌ها از medicines.json
MEDICINES_FILE = Path(settings.BASE_DIR) / "medicines.json"
if MEDICINES_FILE.exists():
    with open(MEDICINES_FILE, "r", encoding="utf-8") as f:
        DATA = json.load(f)
else:
    DATA = {}

# 📷 تصاویر داروها
MEDICINE_IMAGES = DATA.get("medicine_images", {})


def get_all_groups():
    """برگشت تمام گروه‌های دارویی به همراه محصولات"""
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


# 🛒 ویوی خرید داروها
class BuyMedicineView(View):
    def get(self, request):
        groups = get_all_groups()
        return render(request, "buy_medicine.html", {"groups": groups})

    def post(self, request):
        groups = get_all_groups()
        variant_id = request.POST.get("variant_id")
        qty = int(request.POST.get("qty", 1))

        # پیدا کردن محصول
        selected_variant = None
        for group in groups:
            for v in group["variants"]:
                if str(v.get("id")) == str(variant_id):
                    selected_variant = v
                    break

        if not selected_variant:
            return render(request, "buy_medicine.html", {
                "groups": groups,
                "error": "❌ داروی مورد نظر یافت نشد."
            })

        # گرفتن سبد خرید از سشن
        cart = request.session.get("cart", [])

        # اگر قبلاً وجود داشت تعدادش رو زیاد کن
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

        request.session["cart"] = cart
        request.session.modified = True

        # ✅ برگردیم به همون صفحه با پیام موفقیت
        return render(request, "buy_medicine.html", {
            "groups": groups,
            "success": f"✅ {selected_variant['name']} به سبد خرید اضافه شد."
        })


# 🛍 ویوی نمایش سبد خرید
class CartView(View):
    def get(self, request):
        cart = request.session.get("cart", [])
        total = sum(item["qty"] * item["price"] for item in cart)
        return render(request, "cart.html", {"cart": cart, "total": total})
