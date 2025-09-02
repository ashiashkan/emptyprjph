from django.urls import path
from .views import (
    HomeView, LoginView, RegisterView, LogoutView,
    BuyMedicineView, CartView, PaymentView,
    ProfileView, OrderHistoryView, AdminPanelView,
    GuideView, SupportView, ChangeLanguageView
)
from . import views
urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/', views.add_to_cart_view, name='add_to_cart'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('payment/<uuid:order_id>/', views.payment_view, name='payment'),
    path('payment/<uuid:order_id>/check/', views.check_payment_ajax, name='check_payment'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('profile/', views.profile_view, name='profile'),
    path('logout/', views.logout_view, name='logout'),

    # 👨‍💻 پنل مدیریت + راهنما + پشتیبانی
    path('admin-panel/', AdminPanelView.as_view(), name='admin_panel'),
    path('guide/', GuideView.as_view(), name='guide'),
    path('support/', SupportView.as_view(), name='support'),
    path('change-language/', ChangeLanguageView.as_view(), name='change_language'),
]
