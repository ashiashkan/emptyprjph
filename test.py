# views.py  ——— imports بالا:
import re
from django.views.decorators.http import require_http_methods

# ——— Dataclasses: گروه یک فیلد id هم داشته باشد (برای سازگاری با قالب):
@dataclass
class LocalizedGroup:
    key: str
    id: str        # به‌منظور سازگاری با قالب
    name: str
    variants: List[LocalizedItem] = field(default_factory=list)

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

# ——— ویو خرید دارو (GET + POST برای افزودن سریع به سبد):
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
