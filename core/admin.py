from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Order

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('id', 'username', 'phone', 'language', 'is_staff', 'is_superuser')
    search_fields = ('username', 'phone', 'address')
    fieldsets = UserAdmin.fieldsets + (
        ('Extra', {'fields': ('phone', 'address', 'language', 'logout_history')}),
    )

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'total_amount', 'currency', 'status', 'created_at')
    search_fields = ('user__username', 'user__phone', 'crypto_address')
    list_filter = ('status', 'currency', 'created_at')
