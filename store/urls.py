from django.urls import path
from . import views

urlpatterns =[
	path('', views.store, name="store"),
	path('cart/', views.cart, name="cart"),
	path('checkout/', views.checkout, name="checkout"),

	path('update_item/', views.updateItem, name="update_item"),
	# path('process_order/', views.processOrder, name="process_order"),
	path('new_product/', views.new_product, name="new_product"),
	path('login/', views.user_login, name='login'),
	path('logout/', views.logout_view, name='logout'),
	path('register/', views.user_register, name='register'),
	path('product/<int:pk>/', views.product_detail, name='product_detail'),
	path('search/', views.search_results, name='search_results'),
	
	# Mpesa payment URLs
	path('mpesa/initiate/', views.initiate_mpesa_payment, name='initiate_mpesa'),
	path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
	path('mpesa/status/<str:checkout_request_id>/', views.check_payment_status, name='check_payment_status'),
	path('payment/success/<int:order_id>/', views.payment_success, name='payment_success'),
	path('payment/failed/<int:order_id>/', views.payment_failed, name='payment_failed'),
]