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
]