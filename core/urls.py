# urls.py  (فقط اضافه‌شدن payment)
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("guide/", views.guide, name="guide"),
    path("support/", views.support, name="support"),

    path("buy-medicine/", views.buy_medicine, name="buy_medicine"),
    path("item/<str:item_id>/", views.medicine_detail, name="medicine_detail"),

    path('cart/add/', views.add_to_cart, name='cart_add'),
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/', views.cart_detail, name='cart_detail'),
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/<str:item_id>/", views.cart_add, name="cart_add"),
    path("cart/update/<str:item_id>/", views.cart_update, name="cart_update"),

    path("checkout/", views.checkout, name="checkout"),
    path("payment/<uuid:order_id>/", views.payment, name="payment"),  # ⬅️ اضافه شد

    path("orders/", views.order_history, name="order_history"),

    path("login/", views.login_view, name="login"),
    path("login/submit/", views.login_submit, name="login_submit"),
    path("register/", views.register_view, name="register_view"),
    path("register/submit/", views.register_submit, name="register_submit"),
    path("logout/", views.logout_view, name="logout"),

    path("profile/", views.profile, name="profile"),

    path("lang/", views.set_language, name="set_language"),

    path("admin-panel/", views.admin_panel, name="admin_panel"),
    path("admin-panel/export-csv/", views.admin_export_orders_csv, name="admin_export_orders_csv"),

    path("api/search/", views.api_search, name="api_search"),
]
