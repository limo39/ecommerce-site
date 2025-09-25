from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import logging

from .models import * 
from .services.mpesa_service import MpesaService
from .forms import ProductForm, UserRegistrationForm

from django.contrib.auth import authenticate, logout, login
from django.shortcuts import render, redirect

from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required

logger = logging.getLogger(__name__)



def logout_view(request):
    logout(request)
    return redirect('store') 

def user_register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            # Redirect to a success page.
            return redirect('login')  # Adjust 'login' to your login URL name
    else:
        form = UserRegistrationForm()
    return render(request, 'register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Redirect to a success page.
            return redirect('store')  
        else:
            # Return an 'invalid login' error message.
            return render(request, 'login.html', {'error_message': 'Invalid login'})
    else:
        return render(request, 'login.html')


def store(request):
	products = Product.objects.all()
	if request.user.is_authenticated:
		user = request.user
		customer, created = Customer.objects.get_or_create(user=user)
		order, created = Order.objects.get_or_create(customer=customer, complete=False)
		items = order.orderitem_set.all()
		cartItems = order.get_cart_items
	else:
		items = []
		order = {'get_cart_total':0, 'get_cart_items':0}
		cartItems = order['get_cart_items']


	products = Product.objects.all()
	context = {'products':products, 'cartItems':cartItems}
	return render(request, 'store/store.html', context)

def cart(request):
    if request.user.is_authenticated:
        customer = request.user.customer
        order, created = Order.objects.get_or_create(customer=customer, complete=False)
        items = order.orderitem_set.all()
        cartItems = order.get_cart_items
        user = request.user.username
    else:
        items = []
        order = {'get_cart_total':0, 'get_cart_items':0}
        cartItems = order['get_cart_items']
        user = 'AnonymousUser'
    context = {'items':items, 'order':order, 'cartItems':cartItems, 'user':user}
    return render(request, 'store/cart.html', context)


def checkout(request):
    if request.user.is_authenticated:
        customer = request.user.customer
        order, created = Order.objects.get_or_create(customer=customer, complete=False)
        items = order.orderitem_set.all()
        cartItems = order.get_cart_items
    else:
        items = []
        order = {'get_cart_total':0, 'get_cart_items':0}
        cartItems = order['get_cart_items']

    context = {'items': items, 'order': order, 'cartItems': cartItems}
    return render(request, 'store/checkout.html', context)


def updateItem(request):
	data = json.loads(request.body)
	productId = data['productId']
	action = data['action']
	print('Action:', action)
	print('Product:', productId)

	customer = request.user.customer
	product = Product.objects.get(id=productId)
	order, created = Order.objects.get_or_create(customer=customer, complete=False)

	orderItem, created = OrderItem.objects.get_or_create(order=order, product=product)

	if action == 'add':
		orderItem.quantity = (orderItem.quantity + 1)
	elif action == 'remove':
		orderItem.quantity = (orderItem.quantity - 1)

	orderItem.save()

	if orderItem.quantity <= 0:
		orderItem.delete()

	return JsonResponse('Item was added', safe=False)

	
@login_required
@staff_member_required
def new_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.save()
            return redirect('product_detail', product.id)
    else:
        form = ProductForm()
    return render(request, 'new_product.html', {'form': form})

def product_detail(request, pk):
    product = Product.objects.get(pk=pk)
    return render(request, 'product_detail.html', {'product': product})

def search_results(request):
    query = request.GET.get('q')
    results = Product.objects.filter(name__icontains=query) if query else []
    return render(request, 'search_results.html', {'query': query, 'results': results})


@require_http_methods(["POST"])
@login_required
def initiate_mpesa_payment(request):
    """
    Initiate Mpesa STK Push payment
    """
    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number')
        order_id = data.get('order_id')
        
        if not phone_number or not order_id:
            return JsonResponse({
                'success': False,
                'error': 'Phone number and order ID are required'
            }, status=400)
        
        # Get the order
        try:
            order = Order.objects.get(id=order_id, customer=request.user.customer, complete=False)
        except Order.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Order not found'
            }, status=404)
        
        # Validate phone number
        mpesa_service = MpesaService()
        is_valid, formatted_phone = mpesa_service.validate_phone_number(phone_number)
        
        if not is_valid:
            return JsonResponse({
                'success': False,
                'error': 'Invalid phone number format. Use format: 0712345678'
            }, status=400)
        
        # Check if there's already a pending Mpesa transaction for this order
        existing_transaction = MpesaTransaction.objects.filter(
            order=order, 
            status__in=['PENDING', 'SUCCESS']
        ).first()
        
        if existing_transaction:
            if existing_transaction.status == 'SUCCESS':
                return JsonResponse({
                    'success': False,
                    'error': 'This order has already been paid for'
                }, status=400)
            elif existing_transaction.status == 'PENDING':
                return JsonResponse({
                    'success': False,
                    'error': 'Payment is already in progress for this order',
                    'checkout_request_id': existing_transaction.checkout_request_id
                }, status=400)
        
        # Initiate STK Push
        amount = order.get_cart_total
        result = mpesa_service.initiate_stk_push(
            phone_number=formatted_phone,
            amount=amount,
            order_id=order.id,
            account_reference=f"Order-{order.id}"
        )
        
        if result['success']:
            # Create Mpesa transaction record
            mpesa_transaction = MpesaTransaction.objects.create(
                order=order,
                phone_number=formatted_phone,
                amount=amount,
                checkout_request_id=result['checkout_request_id'],
                merchant_request_id=result['merchant_request_id'],
                status='PENDING'
            )
            
            # Update order payment method
            order.payment_method = 'MPESA'
            order.payment_status = 'PENDING'
            order.save()
            
            logger.info(f"STK Push initiated for order {order.id}: {result['checkout_request_id']}")
            
            return JsonResponse({
                'success': True,
                'checkout_request_id': result['checkout_request_id'],
                'customer_message': result.get('customer_message', 'Please check your phone for payment prompt'),
                'order_id': order.id
            })
        else:
            logger.warning(f"STK Push failed for order {order.id}: {result.get('error_message')}")
            return JsonResponse({
                'success': False,
                'error': result.get('customer_message', 'Payment initiation failed'),
                'technical_error': result.get('error_message')
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Mpesa payment initiation error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        }, status=500)


@require_http_methods(["GET"])
@login_required
def check_payment_status(request, checkout_request_id):
    """
    Check the status of an Mpesa payment
    """
    try:
        # Get the transaction
        try:
            transaction = MpesaTransaction.objects.get(
                checkout_request_id=checkout_request_id,
                order__customer=request.user.customer
            )
        except MpesaTransaction.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Transaction not found'
            }, status=404)
        
        # If transaction is already completed, return the status
        if transaction.status in ['SUCCESS', 'FAILED', 'CANCELLED', 'TIMEOUT']:
            return JsonResponse({
                'success': True,
                'status': transaction.status,
                'result_desc': transaction.result_desc,
                'mpesa_receipt_number': transaction.mpesa_receipt_number,
                'order_id': transaction.order.id
            })
        
        # Query Mpesa API for current status
        mpesa_service = MpesaService()
        result = mpesa_service.query_transaction_status(checkout_request_id)
        
        if result['success']:
            # Update transaction based on result
            result_code = result.get('result_code')
            
            if result_code == 0:
                transaction.status = 'SUCCESS'
                transaction.result_code = result_code
                transaction.result_desc = result.get('result_desc', 'Payment successful')
                
                # Update order status
                transaction.order.payment_status = 'PAID'
                transaction.order.complete = True
                transaction.order.save()
                
            elif result_code in [1032, 1037]:  # User cancelled or timeout
                transaction.status = 'CANCELLED'
                transaction.result_code = result_code
                transaction.result_desc = result.get('result_desc', 'Payment cancelled')
                
                # Update order status
                transaction.order.payment_status = 'FAILED'
                transaction.order.save()
                
            elif result_code == 1:  # Insufficient funds or other failure
                transaction.status = 'FAILED'
                transaction.result_code = result_code
                transaction.result_desc = result.get('result_desc', 'Payment failed')
                
                # Update order status
                transaction.order.payment_status = 'FAILED'
                transaction.order.save()
            
            transaction.save()
            
            return JsonResponse({
                'success': True,
                'status': transaction.status,
                'result_desc': transaction.result_desc,
                'mpesa_receipt_number': transaction.mpesa_receipt_number,
                'order_id': transaction.order.id
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Unable to check payment status'
            }, status=500)
            
    except Exception as e:
        logger.error(f"Payment status check error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def mpesa_callback(request):
    """
    Handle Mpesa Daraja API callbacks
    """
    try:
        # Parse callback data
        callback_data = json.loads(request.body)
        logger.info(f"Received Mpesa callback: {callback_data}")
        
        # Process callback using service
        mpesa_service = MpesaService()
        processed_data = mpesa_service.process_callback(callback_data)
        
        if not processed_data.get('checkout_request_id'):
            logger.warning("Callback missing checkout_request_id")
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})
        
        # Find the transaction
        try:
            transaction = MpesaTransaction.objects.get(
                checkout_request_id=processed_data['checkout_request_id']
            )
        except MpesaTransaction.DoesNotExist:
            logger.warning(f"Transaction not found for checkout_request_id: {processed_data['checkout_request_id']}")
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})
        
        # Prevent duplicate processing
        if transaction.status in ['SUCCESS', 'FAILED', 'CANCELLED']:
            logger.info(f"Transaction {transaction.checkout_request_id} already processed")
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})
        
        # Update transaction based on callback
        transaction.result_code = processed_data.get('result_code')
        transaction.result_desc = processed_data.get('result_desc', '')
        
        if processed_data['success']:
            # Payment successful
            transaction.status = 'SUCCESS'
            transaction.mpesa_receipt_number = processed_data.get('mpesa_receipt_number')
            transaction.transaction_date = processed_data.get('transaction_date')
            
            # Update order
            order = transaction.order
            order.payment_status = 'PAID'
            order.complete = True
            order.transaction_id = processed_data.get('mpesa_receipt_number')
            order.save()
            
            logger.info(f"Payment successful for order {order.id}: {transaction.mpesa_receipt_number}")
            
        else:
            # Payment failed
            result_code = processed_data.get('result_code')
            
            if result_code in [1032, 1037]:  # User cancelled or timeout
                transaction.status = 'CANCELLED'
            else:
                transaction.status = 'FAILED'
            
            # Update order
            order = transaction.order
            order.payment_status = 'FAILED'
            order.save()
            
            logger.info(f"Payment failed for order {order.id}: {processed_data.get('result_desc')}")
        
        transaction.save()
        
        # Return success response to Mpesa
        return JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Accepted'
        })
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in Mpesa callback")
        return JsonResponse({
            'ResultCode': 1,
            'ResultDesc': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Mpesa callback processing error: {str(e)}")
        return JsonResponse({
            'ResultCode': 1,
            'ResultDesc': 'Processing failed'
        }, status=500)


def payment_success(request, order_id):
    """
    Payment success page
    """
    try:
        order = get_object_or_404(
            Order, 
            id=order_id, 
            customer=request.user.customer if request.user.is_authenticated else None,
            payment_status='PAID'
        )
        
        context = {
            'order': order,
            'items': order.orderitem_set.all(),
            'mpesa_transaction': getattr(order, 'mpesa_transaction', None)
        }
        return render(request, 'store/payment_success.html', context)
        
    except Exception as e:
        logger.error(f"Payment success page error: {str(e)}")
        return redirect('store')


def payment_failed(request, order_id):
    """
    Payment failure page
    """
    try:
        order = get_object_or_404(
            Order, 
            id=order_id, 
            customer=request.user.customer if request.user.is_authenticated else None
        )
        
        context = {
            'order': order,
            'items': order.orderitem_set.all(),
            'mpesa_transaction': getattr(order, 'mpesa_transaction', None)
        }
        return render(request, 'store/payment_failed.html', context)
        
    except Exception as e:
        logger.error(f"Payment failed page error: {str(e)}")
        return redirect('store')