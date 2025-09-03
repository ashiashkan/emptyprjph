from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),  # اتصال core – بدون تغییر، اما چک شد برای پایداری
]