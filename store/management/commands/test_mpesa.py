from django.core.management.base import BaseCommand
from store.services.mpesa_service import MpesaService
from django.conf import settings

class Command(BaseCommand):
    help = 'Test Mpesa Daraja API credentials and configuration'

    def handle(self, *args, **options):
        self.stdout.write("Testing Mpesa Daraja API Configuration...")
        self.stdout.write("-" * 50)
        
        # Check configuration
        config = settings.MPESA_CONFIG
        self.stdout.write(f"Environment: {config['ENVIRONMENT']}")
        self.stdout.write(f"Shortcode: {config['SHORTCODE']}")
        self.stdout.write(f"Consumer Key: {config['CONSUMER_KEY'][:10]}...")
        self.stdout.write(f"Consumer Secret: {config['CONSUMER_SECRET'][:10]}...")
        self.stdout.write(f"Passkey: {config['PASSKEY'][:20]}...")
        self.stdout.write(f"Callback URL: {config['CALLBACK_URL']}")
        
        # Test credentials
        self.stdout.write("\nTesting credentials...")
        mpesa_service = MpesaService()
        
        try:
            success, message = mpesa_service.test_credentials()
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Credentials test passed: {message}")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"✗ Credentials test failed: {message}")
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Test error: {str(e)}")
            )
        
        # Test phone number validation
        self.stdout.write("\nTesting phone number validation...")
        test_numbers = ['0712345678', '254712345678', '+254712345678', '712345678']
        
        for number in test_numbers:
            is_valid, formatted = mpesa_service.validate_phone_number(number)
            status = "✓" if is_valid else "✗"
            self.stdout.write(f"{status} {number} -> {formatted}")
        
        self.stdout.write("\nTest completed!")
        
        # Ask if user wants to test STK Push
        test_stk = input("\nDo you want to test STK Push? (y/n): ").lower().strip()
        if test_stk == 'y':
            phone = input("Enter test phone number (e.g., 254712345678): ").strip()
            if phone:
                self.stdout.write(f"\nTesting STK Push to {phone}...")
                try:
                    result = mpesa_service.initiate_stk_push(
                        phone_number=phone,
                        amount=1,  # Test with 1 KSh
                        order_id=999,
                        account_reference="TEST-ORDER"
                    )
                    
                    if result['success']:
                        self.stdout.write(
                            self.style.SUCCESS(f"✓ STK Push initiated: {result['checkout_request_id']}")
                        )
                        self.stdout.write(f"Customer message: {result.get('customer_message')}")
                    else:
                        self.stdout.write(
                            self.style.ERROR(f"✗ STK Push failed: {result.get('error_message')}")
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"✗ STK Push error: {str(e)}")
                    )