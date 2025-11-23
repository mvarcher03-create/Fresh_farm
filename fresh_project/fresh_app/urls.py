from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('customer-dashboard/', views.customer_dashboard, name='customer_dashboard'),
    path('my-orders/', views.customer_orders, name='customer_orders'),
    path('shop/', views.shop_now, name='shop_now'),
    path('cart/', views.cart_view, name='cart_view'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/update/', views.cart_update, name='cart_update'),
    path('cart/remove/<int:product_id>/', views.cart_remove, name='cart_remove'),
    path('cart/checkout/', views.cart_checkout, name='cart_checkout'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-products/', views.admin_products, name='admin_products'),
    path('admin-products/add/', views.admin_product_add, name='admin_product_add'),
    path('admin-products/<int:pk>/edit/', views.admin_product_edit, name='admin_product_edit'),
    path('admin-products/<int:pk>/stock/', views.admin_product_stock, name='admin_product_stock'),
    path('admin-products/<int:pk>/toggle/', views.admin_product_toggle, name='admin_product_toggle'),
    path('admin-products/<int:pk>/delete/', views.admin_product_delete, name='admin_product_delete'),
    path('admin-orders/', views.admin_orders, name='admin_orders'),
    path('admin-orders/<int:order_id>/update-status/', views.admin_order_update_status, name='admin_order_update_status'),
    path('admin-customers/', views.admin_customers, name='admin_customers'),
    path('admin-reports/', views.admin_reports, name='admin_reports'),
]