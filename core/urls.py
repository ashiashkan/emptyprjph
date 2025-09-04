from django.urls import path
from . import views

# app_name = "core"  # commented out

urlpatterns = [
    # صفحه اصلی — تابعی در views به نام `home`
    path("", views.home, name="home"),

    # راهنما و پشتیبانی
    path("guide/", views.guide, name="guide"),
    path("support/", views.support, name="support"),

    # لیست و جستجوی دارو (تابعی: buy_medicine)
    path("buy-medicine/", views.buy_medicine, name="buy_medicine"),
    path("item/<str:item_id>/", views.medicine_detail, name="medicine_detail"),

    # سبد خرید و API های مربوطه
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/<str:item_id>/", views.cart_add, name="cart_add"),
    path("cart/update/<str:item_id>/", views.cart_update, name="cart_update"),

    # پرداخت / تسویه (در views: checkout)
    path("checkout/", views.checkout, name="checkout"),

    # تاریخچه سفارش (session-based)
    path("orders/", views.order_history, name="order_history"),

    # احراز هویت (توابع و فرم‌های داخلی)
    path("login/", views.login_view, name="login"),
    path("login/submit/", views.login_submit, name="login_submit"),
    path("register/", views.register_view, name="register_view"),
    path("register/submit/", views.register_submit, name="register_submit"),
    path("logout/", views.logout_view, name="logout"),

    # پروفایل
    path("profile/", views.profile, name="profile"),

    # مدیریت زبان
    path("lang/", views.set_language, name="set_language"),

    # پنل ادمین و اکسپورت CSV
    path("admin-panel/", views.admin_panel, name="admin_panel"),
    path("admin-panel/export-csv/", views.admin_export_orders_csv, name="admin_export_orders_csv"),
    path("payment/<uuid:order_id>/", views.payment, name="payment"),
    # API ساده جستجو
    path("api/search/", views.api_search, name="api_search"),
]