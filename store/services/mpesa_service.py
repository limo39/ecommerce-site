import requests
import base64
import json
from datetime import datetime
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class MpesaService:
    """
    Service class for handling Mpesa Daraja API interactions
    """
    
    def __init__(self):
        self.config = settings.MPESA_CONFIG
        self.urls = settings.MPESA_URLS[self.config['ENVIRONMENT']]
        self.access_token = None
        self.token_expires_at = None
    
    def get_access_token(self):
        """
        Get OAuth2 access token from Daraja API
        """
        try:
            # Check if we have a valid cached token
            if (self.access_token and self.token_expires_at and 
                timezone.now() < self.token_expires_at):
                return self.access_token
            
            # Create credentials string
            credentials = f"{self.config['CONSUMER_KEY']}:{self.config['CONSUMER_SECRET']}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(self.urls['auth'], headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            self.access_token = data['access_token']
            
            # Token expires in 1 hour, cache for 55 minutes to be safe
            expires_in_seconds = int(data.get('expires_in', 3600)) - 300
            self.token_expires_at = timezone.now() + timezone.timedelta(seconds=expires_in_seconds)
            
            logger.info("Successfully obtained Mpesa access token")
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get Mpesa access token: {str(e)}")
            raise Exception(f"Authentication failed: {str(e)}")
        except KeyError as e:
            logger.error(f"Invalid response format from Mpesa auth: {str(e)}")
            raise Exception("Invalid authentication response")
    
    def initiate_stk_push(self, phone_number, amount, order_id, account_reference=None):
        """
        Initiate STK Push payment request
        
        Args:
            phone_number (str): Customer phone number (254XXXXXXXXX format)
            amount (float): Amount to charge
            order_id (int): Order ID for reference
            account_reference (str): Optional account reference
            
        Returns:
            dict: Response from Daraja API
        """
        try:
            access_token = self.get_access_token()
            
            # Format phone number to 254XXXXXXXXX
            if phone_number.startswith('0'):
                phone_number = '254' + phone_number[1:]
            elif phone_number.startswith('+254'):
                phone_number = phone_number[1:]
            elif not phone_number.startswith('254'):
                phone_number = '254' + phone_number
            
            # Generate timestamp
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            
            # Generate password
            shortcode = self.config['SHORTCODE']
            passkey = self.config['PASSKEY']
            password_string = f"{shortcode}{passkey}{timestamp}"
            password = base64.b64encode(password_string.encode()).decode()
            
            # Prepare request payload
            payload = {
                "BusinessShortCode": shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": max(1, int(float(amount))),  # Ensure minimum amount of 1
                "PartyA": phone_number,
                "PartyB": shortcode,
                "PhoneNumber": phone_number,
                "CallBackURL": self.config['CALLBACK_URL'],
                "AccountReference": account_reference or f"Order-{order_id}",
                "TransactionDesc": f"Payment for Order #{order_id}"
            }
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            logger.info(f"Initiating STK Push for phone {phone_number}, amount {amount}")
            
            logger.info(f"STK Push payload: {json.dumps(payload, indent=2)}")
            logger.info(f"STK Push headers: {headers}")
            
            response = requests.post(
                self.urls['stk_push'], 
                json=payload, 
                headers=headers, 
                timeout=30
            )
            
            logger.info(f"STK Push response status: {response.status_code}")
            logger.info(f"STK Push response text: {response.text}")
            
            if response.status_code != 200:
                logger.error(f"STK Push API error: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error_message': f"API Error {response.status_code}: {response.text}",
                    'customer_message': 'Payment service temporarily unavailable. Please try again.'
                }
            
            data = response.json()
            
            if data.get('ResponseCode') == '0':
                logger.info(f"STK Push initiated successfully: {data.get('CheckoutRequestID')}")
                return {
                    'success': True,
                    'checkout_request_id': data.get('CheckoutRequestID'),
                    'merchant_request_id': data.get('MerchantRequestID'),
                    'response_code': data.get('ResponseCode'),
                    'response_description': data.get('ResponseDescription'),
                    'customer_message': data.get('CustomerMessage')
                }
            else:
                logger.warning(f"STK Push failed: {data}")
                return {
                    'success': False,
                    'error_code': data.get('ResponseCode'),
                    'error_message': data.get('ResponseDescription', 'Unknown error'),
                    'customer_message': data.get('CustomerMessage', 'Payment request failed')
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"STK Push request failed: {str(e)}")
            return {
                'success': False,
                'error_message': f"Network error: {str(e)}",
                'customer_message': 'Payment request failed. Please try again.'
            }
        except Exception as e:
            logger.error(f"STK Push unexpected error: {str(e)}")
            return {
                'success': False,
                'error_message': f"Unexpected error: {str(e)}",
                'customer_message': 'Payment request failed. Please try again.'
            }
    
    def query_transaction_status(self, checkout_request_id):
        """
        Query the status of an STK Push transaction
        
        Args:
            checkout_request_id (str): CheckoutRequestID from STK Push response
            
        Returns:
            dict: Transaction status response
        """
        try:
            access_token = self.get_access_token()
            
            # Generate timestamp and password
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            shortcode = self.config['SHORTCODE']
            passkey = self.config['PASSKEY']
            password_string = f"{shortcode}{passkey}{timestamp}"
            password = base64.b64encode(password_string.encode()).decode()
            
            payload = {
                "BusinessShortCode": shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id
            }
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                self.urls['query'], 
                json=payload, 
                headers=headers, 
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Transaction status query result: {data}")
            
            return {
                'success': True,
                'result_code': data.get('ResultCode'),
                'result_desc': data.get('ResultDesc'),
                'checkout_request_id': data.get('CheckoutRequestID'),
                'merchant_request_id': data.get('MerchantRequestID')
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Transaction status query failed: {str(e)}")
            return {
                'success': False,
                'error_message': f"Query failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Transaction status query unexpected error: {str(e)}")
            return {
                'success': False,
                'error_message': f"Unexpected error: {str(e)}"
            }
    
    def process_callback(self, callback_data):
        """
        Process callback data from Daraja API
        
        Args:
            callback_data (dict): Callback data from Mpesa
            
        Returns:
            dict: Processed callback information
        """
        try:
            stk_callback = callback_data.get('Body', {}).get('stkCallback', {})
            
            result_code = stk_callback.get('ResultCode')
            result_desc = stk_callback.get('ResultDesc', '')
            checkout_request_id = stk_callback.get('CheckoutRequestID')
            merchant_request_id = stk_callback.get('MerchantRequestID')
            
            processed_data = {
                'checkout_request_id': checkout_request_id,
                'merchant_request_id': merchant_request_id,
                'result_code': result_code,
                'result_desc': result_desc,
                'success': result_code == 0
            }
            
            # Extract callback metadata if payment was successful
            if result_code == 0:
                callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
                
                for item in callback_metadata:
                    name = item.get('Name')
                    value = item.get('Value')
                    
                    if name == 'Amount':
                        processed_data['amount'] = value
                    elif name == 'MpesaReceiptNumber':
                        processed_data['mpesa_receipt_number'] = value
                    elif name == 'TransactionDate':
                        # Convert timestamp to datetime
                        if value:
                            try:
                                processed_data['transaction_date'] = datetime.strptime(
                                    str(value), '%Y%m%d%H%M%S'
                                )
                            except ValueError:
                                processed_data['transaction_date'] = timezone.now()
                    elif name == 'PhoneNumber':
                        processed_data['phone_number'] = value
            
            logger.info(f"Processed callback for {checkout_request_id}: {processed_data}")
            return processed_data
            
        except Exception as e:
            logger.error(f"Callback processing error: {str(e)}")
            return {
                'success': False,
                'error_message': f"Callback processing failed: {str(e)}"
            }
    
    def validate_phone_number(self, phone_number):
        """
        Validate Kenyan phone number format
        
        Args:
            phone_number (str): Phone number to validate
            
        Returns:
            tuple: (is_valid, formatted_number)
        """
        if not phone_number:
            return False, None
        
        # Remove spaces and special characters
        phone_number = ''.join(filter(str.isdigit, phone_number))
        
        # Check various formats and convert to 254XXXXXXXXX
        if phone_number.startswith('254') and len(phone_number) == 12:
            return True, phone_number
        elif phone_number.startswith('0') and len(phone_number) == 10:
            return True, '254' + phone_number[1:]
        elif len(phone_number) == 9:
            return True, '254' + phone_number
        
        return False, None
    
    def test_credentials(self):
        """
        Test if the Mpesa credentials are working
        """
        try:
            access_token = self.get_access_token()
            logger.info(f"Credentials test successful. Token: {access_token[:20]}...")
            return True, "Credentials are valid"
        except Exception as e:
            logger.error(f"Credentials test failed: {str(e)}")
            return False, str(e)