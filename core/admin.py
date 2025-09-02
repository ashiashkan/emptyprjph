from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import CustomUser, Order, OrderItem, Customer

# unregister اگر قبلاً ثبت شده
try:
    admin.site.unregister(CustomUser)
except admin.sites.NotRegistered:
    pass

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'address', 'language')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    ordering = ('phone',)
    list_display = ('phone', 'first_name', 'last_name', 'is_staff')
    search_fields = ('phone', 'first_name', 'last_name')
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'password1', 'password2'),
        }),
    )

# ثبت مدل‌های دیگر بدون duplicate
try:
    admin.site.unregister(Order)
except admin.sites.NotRegistered:
    pass
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'user', 'total_amount', 'status', 'created_at')
    list_filter = ('status', 'currency', 'created_at')
    readonly_fields = ('deposit_address',)

    def total_amount(self, obj):
        if hasattr(obj, 'amount_usd') and obj.amount_usd is not None:
            return f"${obj.amount_usd}"
        total = 0
        for it in obj.items.all():
            total += (it.unit_price or 0) * (it.quantity or 0)
        return f"${total:.2f}"
    total_amount.short_description = 'مبلغ کل'

try:
    admin.site.unregister(OrderItem)
except admin.sites.NotRegistered:
    pass
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit_price', 'quantity', 'order')

try:
    admin.site.unregister(Customer)
except admin.sites.NotRegistered:
    pass
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'first_name', 'last_name')