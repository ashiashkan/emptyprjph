# core/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import CustomUser, Order, OrderItem, Customer

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    # فیلدهایی که در لیست ادمین نمایش داده می‌شوند (تنظیم به فیلدهای واقعی)
    list_display = ('username', 'email', 'is_staff', 'language_display')
    list_filter = ('is_staff', 'is_superuser', 'is_active')

    # اگر می‌خواهی 'language' را داشته باشی و مدل این فیلد را نداشته باشد،
    # این متد مقدار پیش‌فرض یا مقدار از metadata را نمایش می‌دهد.
    def language_display(self, obj):
        # اگر در مدل فیلد language وجود دارد، آن را برگردان
        if hasattr(obj, 'language'):
            return getattr(obj, 'language')
        # یا اگر در پروفایل/metadata ذخیره شده
        profile = getattr(obj, 'customer_profile', None)
        if profile and getattr(profile, 'language', None):
            return profile.language
        return '-'  # مقدار پیش‌فرض
    language_display.short_description = 'زبان'

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'user', 'total_amount', 'status', 'created_at')
    list_filter = ('status', 'currency', 'created_at')
    readonly_fields = ('deposit_address',)

    def total_amount(self, obj):
        """
        اگر مدل Order فیلد amount_usd دارد، از آن استفاده کن.
        در غیر اینصورت مجموع آیتم‌ها را جمع می‌زنیم.
        """
        # اگر فیلد amount_usd داشته باشیم:
        if hasattr(obj, 'amount_usd') and obj.amount_usd is not None:
            return f"${obj.amount_usd}"
        # محاسبه از آیتم‌ها
        total = 0
        for it in getattr(obj, 'items', []).all():
            total += (it.unit_price or 0) * (it.quantity or 0)
        return f"${total:.2f}"
    total_amount.short_description = 'مبلغ کل'

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit_price', 'quantity', 'order')

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'first_name', 'last_name')
