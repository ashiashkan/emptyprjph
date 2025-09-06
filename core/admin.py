from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms
from django.core.exceptions import ValidationError
import re
from .models import CustomUser, Order, OrderItem, Customer

# unregister اگر قبلاً ثبت شده
try:
    admin.site.unregister(CustomUser)
except admin.sites.NotRegistered:
    pass

class CustomUserAdminForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = '__all__'
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if not re.match(r'^\+?1?\d{9,15}$', phone):
            raise ValidationError('Phone number must be entered in the format: "+999999999". Up to 15 digits allowed.')
        return phone

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    form = CustomUserAdminForm
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'address', 'language')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')}),
        ('Logout History', {'fields': ('logout_history',)}),
    )
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('phone',)
    list_display = ('phone', 'first_name', 'last_name', 'is_staff', 'created_at')
    search_fields = ('phone', 'first_name', 'last_name', 'email')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'language')
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'password1', 'password2', 'first_name', 'last_name', 'email', 'address', 'language'),
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

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'first_name', 'last_name')