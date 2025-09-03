from django.urls import path
from .views import (  # import مستقیم از views.py
    HomeView, LoginView, RegisterView, LogoutView,
    BuyMedicineView, CartView, PaymentView,
    ProfileView, OrderHistoryView, AdminPanelView,
    GuideView, SupportView, ChangeLanguageView,
    checkout_view, add_to_cart  # add_to_cart رو اضافه کن
)

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('login/', LoginView.as_view(), name='login'),
    path('checkout/', checkout_view, name='checkout'),
    path('register/', RegisterView.as_view(), name='register'),
    path('logout/', LogoutView.as_view(), name='logout'),

    # 🛒 داروها و سبد خرید
    path('buy/', BuyMedicineView.as_view(), name='buy_medicine'),
    path('cart/', CartView.as_view(), name='cart'),
    path('add-to-cart/', add_to_cart, name='add_to_cart'),  # URL جدید برای افزودن به سبد (POST)

    # 💳 پرداخت و سفارش‌ها
    path('payment/', PaymentView.as_view(), name='payment'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('history/', OrderHistoryView.as_view(), name='order_history'),

    # 👨‍💻 پنل مدیریت + راهنما + پشتیبانی
    path('admin-panel/', AdminPanelView.as_view(), name='admin_panel'),
    path('guide/', GuideView.as_view(), name='guide'),
    path('support/', SupportView.as_view(), name='support'),
    path('change-language/', ChangeLanguageView.as_view(), name='change_language'),
]