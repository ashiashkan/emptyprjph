from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
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
    order_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    amount_usd = models.DecimalField(max_digits=12, decimal_places=2)
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
