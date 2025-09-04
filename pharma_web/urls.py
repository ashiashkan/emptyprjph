from django.contrib import admin
from django.urls import path, include
import core.views as core_views

urlpatterns = [
    # مسیر اصلی که قالب‌ها روی آن حساب باز می‌کنند
    path('', core_views.home, name='home'),

    # مسیر ادمین
    path('admin/', admin.site.urls),

    # include کردن app core بدون namespace تا نام‌های ساده در دسترس باشند
    path('', include('core.urls')),
]