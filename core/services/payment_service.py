# services/payment_service.py
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
import requests

from ..models import (
    PaymentProvider, PaymentTransaction, PaymentNotification, 
    Bill, BopsBills, PropertyOwner
)

# Set up logging
logger = logging.getLogger(__name__)

class KowriPaymentService:
    """Service class for Kowri payment integration"""
    
    # Constants
    ALLOWED_BILL_TYPES = ['property', 'business']
    REQUIRED_NOTIFICATION_FIELDS = ['transaction_id', 'bill_reference', 'amount']
    
    def __init__(self, provider=None):
        """Initialize the payment service with a provider"""
        self.provider = self._get_provider(provider)
        self.base_url = self.provider.api_base_url.rstrip('/')
        self.api_key = self.provider.api_key
        self.api_secret = self.provider.api_secret
        
        logger.info(f"KowriPaymentService initialized with provider: {self.provider.name}")
    
    def _get_provider(self, provider):
        """Get or fetch the payment provider"""
        if provider:
            return provider
        
        provider = PaymentProvider.objects.filter(
            provider_type='kowri', 
            is_active=True
        ).first()
        
        if not provider:
            error_msg = "No active Kowri payment provider configured"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        return provider
    
    def generate_headers(self) -> Dict[str, str]:
        """Generate authentication headers for Kowri API"""
        try:
            timestamp = str(int(datetime.now().timestamp()))
            
            # Create HMAC signature
            message = f"{timestamp}{self.api_key}"
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return {
                'Authorization': f'Kowri {self.api_key}:{signature}',
                'Content-Type': 'application/json',
                'X-Timestamp': timestamp,
                'User-Agent': 'SKTLIVE-Payment-Service/1.0'
            }
        except Exception as e:
            logger.error(f"Error generating headers: {str(e)}")
            raise
    
    def lookup_bill(self, bill_reference: str, bill_type: str = 'property') -> Dict[str, Any]:
        """
        Look up bill details by reference
        This endpoint will be called by Kowri when payer initiates payment
        """
        try:
            # Validate bill type
            if bill_type not in self.ALLOWED_BILL_TYPES:
                return {
                    'success': False,
                    'error': f'Invalid bill type. Must be one of: {", ".join(self.ALLOWED_BILL_TYPES)}'
                }
            
            # Look up based on bill type
            if bill_type == 'property':
                return self._lookup_property_bill(bill_reference)
            else:  # business
                return self._lookup_business_bill(bill_reference)
                
        except Exception as e:
            logger.exception(f"Unexpected error in bill lookup: {str(e)}")
            return {
                'success': False,
                'error': 'An unexpected error occurred during bill lookup'
            }
    
    def _lookup_property_bill(self, bill_reference: str) -> Dict[str, Any]:
        """Look up a property bill"""
        try:
            # Try to find by bill number or ID
            bill = Bill.objects.select_related(
                'property', 
                'billing_cycle',
                'property__zone'
            ).prefetch_related(
                'property__owners'
            ).get(
                Q(bill_number=bill_reference) | 
                Q(id=bill_reference) |
                Q(property__property_id=bill_reference)
            )
            
            # Check if bill is already paid
            if bill.status == 'paid':
                return {
                    'success': False,
                    'error': 'This bill has already been paid',
                    'bill_status': bill.status
                }
            
            # Get primary owner info
            primary_owner = bill.property.owners.filter(
                is_primary_owner=True
            ).first()
            
            # Build response
            response = {
                'success': True,
                'bill_reference': bill.bill_number,
                'bill_type': 'property',
                'amount_due': str(bill.total_amount),
                'amount_paid': str(bill.paid_amount) if hasattr(bill, 'paid_amount') else '0.00',
                'balance_due': str(bill.total_amount - (bill.paid_amount if hasattr(bill, 'paid_amount') else 0)),
                'currency': 'GHS',
                'payer_name': primary_owner.owner_name if primary_owner else 'Property Owner',
                'payer_phone': primary_owner.phone_number if primary_owner else '',
                'payer_email': primary_owner.email if primary_owner else '',
                'description': f"Property Tax - {bill.property.address}",
                'due_date': bill.due_date.strftime('%Y-%m-%d'),
                'bill_date': bill.generated_date.strftime('%Y-%m-%d'),
                'status': bill.status,
                'metadata': {
                    'bill_id': bill.id,
                    'bill_number': bill.bill_number,
                    'property_id': bill.property.id,
                    'property_address': bill.property.address,
                    'property_type': bill.property.property_type.name if bill.property.property_type else '',
                    'zone': bill.property.zone.name if bill.property.zone else '',
                    'billing_cycle': bill.billing_cycle.name if bill.billing_cycle else '',
                }
            }
            
            logger.info(f"Property bill lookup successful: {bill.bill_number}")
            return response
            
        except Bill.DoesNotExist:
            logger.warning(f"Property bill not found: {bill_reference}")
            return {
                'success': False,
                'error': 'Property bill not found'
            }
        except Exception as e:
            logger.exception(f"Error looking up property bill: {str(e)}")
            return {
                'success': False,
                'error': f'Error looking up property bill: {str(e)}'
            }
    
    def _lookup_business_bill(self, bill_reference: str) -> Dict[str, Any]:
        """Look up a business bill"""
        try:
            # Try to find by bill number or ID
            bill = BopsBills.objects.select_related(
                'business'
            ).get(
                Q(bill_number=bill_reference) | 
                Q(id=bill_reference) |
                Q(business__account_number=bill_reference)
            )
            
            # Check if bill is already paid
            if bill.status == 'paid':
                return {
                    'success': False,
                    'error': 'This bill has already been paid',
                    'bill_status': bill.status
                }
            
            # Build response
            response = {
                'success': True,
                'bill_reference': bill.bill_number,
                'bill_type': 'business',
                'amount_due': str(bill.total_amount),
                'amount_paid': str(bill.tax_amount) if hasattr(bill, 'tax_amount') else '0.00',
                'balance_due': str(bill.total_amount - (bill.tax_amount if hasattr(bill, 'tax_amount') else 0)),
                'currency': 'GHS',
                'payer_name': bill.business.business_name,
                'payer_phone': bill.business.phone_number or bill.business.phone_number_primary or '',
                'payer_email': bill.business.business_email or bill.business.email or '',
                'description': f"Business Operating Permit - {bill.business.business_name}",
                'due_date': bill.due_date.strftime('%Y-%m-%d'),
                'bill_date': bill.generated_date.strftime('%Y-%m-%d'),
                'status': bill.status,
                'metadata': {
                    'bill_id': bill.id,
                    'bill_number': bill.bill_number,
                    'business_id': bill.business.id,
                    'business_name': bill.business.business_name,
                    'account_number': bill.business.account_number,
                    'business_category': bill.business.business_category,
                }
            }
            
            logger.info(f"Business bill lookup successful: {bill.bill_number}")
            return response
            
        except BopsBills.DoesNotExist:
            logger.warning(f"Business bill not found: {bill_reference}")
            return {
                'success': False,
                'error': 'Business bill not found'
            }
        except Exception as e:
            logger.exception(f"Error looking up business bill: {str(e)}")
            return {
                'success': False,
                'error': f'Error looking up business bill: {str(e)}'
            }
    
    def validate_notification(self, notification_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate incoming payment notification"""
        # Check required fields
        for field in self.REQUIRED_NOTIFICATION_FIELDS:
            if field not in notification_data:
                return False, f"Missing required field: {field}"
        
        # Validate amount is positive
        try:
            amount = Decimal(str(notification_data.get('amount', '0')))
            if amount <= 0:
                return False, "Amount must be positive"
        except:
            return False, "Invalid amount format"
        
        # Validate bill type if provided
        bill_type = notification_data.get('bill_type', 'property')
        if bill_type not in self.ALLOWED_BILL_TYPES:
            return False, f"Invalid bill type. Must be one of: {', '.join(self.ALLOWED_BILL_TYPES)}"
        
        return True, "Valid"
    
    
    @transaction.atomic
    def process_payment_notification(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process payment notification from Kowri
        This endpoint receives payment confirmation
        """
        # Validate notification
        is_valid, error_msg = self.validate_notification(notification_data)
        if not is_valid:
            logger.error(f"Invalid notification: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        
        # Log the notification
        notification = PaymentNotification.objects.create(
            provider=self.provider,
            raw_data=notification_data,
            processed=False
        )
        
        try:
            # Extract data
            provider_transaction_id = notification_data.get('transaction_id')
            bill_reference = notification_data.get('bill_reference')
            bill_type = notification_data.get('bill_type', 'property')
            amount = Decimal(str(notification_data.get('amount', '0')))
            status = notification_data.get('status', 'completed').lower()
            payment_method = notification_data.get('payment_method', '')
            payment_channel = notification_data.get('channel', '')
            payer_info = notification_data.get('payer', {})
            
            # Look up the bill to verify it exists
            lookup_result = self.lookup_bill(bill_reference, bill_type)
            if not lookup_result.get('success'):
                raise ValueError(f"Bill not found: {lookup_result.get('error')}")
            
            # Check if amount matches
            amount_due = Decimal(lookup_result['amount_due'])
            if abs(amount - amount_due) > Decimal('0.01'):  # Allow small rounding differences
                logger.warning(f"Amount mismatch: paid={amount}, due={amount_due}")
                # Still process but log the discrepancy
            
            # Get or create transaction
            transaction_obj, created = PaymentTransaction.objects.get_or_create(
                provider_transaction_id=provider_transaction_id,
                defaults={
                    'transaction_id': self.generate_transaction_id(),
                    'bill_type': bill_type,
                    'amount': amount,
                    'provider': self.provider,
                    'status': 'pending',
                    'payment_method': payment_method,
                    'payment_channel': payment_channel,
                    'payer_name': payer_info.get('name', ''),
                    'payer_phone': payer_info.get('phone', ''),
                    'payer_email': payer_info.get('email', ''),
                    'metadata': notification_data,
                }
            )
            
            # Process based on status
            if status in ['success', 'completed']:
                self._process_successful_payment(transaction_obj, bill_type, bill_reference, amount)
            elif status == 'failed':
                self._process_failed_payment(transaction_obj, notification_data.get('error_message'))
            elif status == 'pending':
                transaction_obj.status = 'pending'
                transaction_obj.save()
                logger.info(f"Payment pending: {provider_transaction_id}")
            else:
                logger.warning(f"Unknown payment status: {status}")
            
            # Mark notification as processed
            notification.processed = True
            notification.transaction = transaction_obj
            notification.save()
            
            return {
                'success': True,
                'transaction_id': transaction_obj.transaction_id,
                'status': transaction_obj.status,
                'message': f'Payment processed successfully'
            }
            
        except Bill.DoesNotExist:
            error_msg = f"Bill not found: {bill_reference}"
            logger.error(error_msg)
            notification.error = error_msg
            notification.save()
            return {'success': False, 'error': error_msg}
            
        except BopsBills.DoesNotExist:
            error_msg = f"Business bill not found: {bill_reference}"
            logger.error(error_msg)
            notification.error = error_msg
            notification.save()
            return {'success': False, 'error': error_msg}
            
        except ValueError as e:
            logger.error(f"Validation error: {str(e)}")
            notification.error = str(e)
            notification.save()
            return {'success': False, 'error': str(e)}
            
        except Exception as e:
            logger.exception(f"Unexpected error processing payment: {str(e)}")
            notification.error = str(e)
            notification.save()
            return {
                'success': False, 
                'error': 'An unexpected error occurred while processing the payment'
            }
    
    def _process_successful_payment(self, transaction_obj, bill_type, bill_reference, amount):
        """Process a successful payment"""
        transaction_obj.status = 'completed'
        transaction_obj.completed_at = timezone.now()
        
        # Update the corresponding bill
        if bill_type == 'property':
            bill = Bill.objects.get(bill_number=bill_reference)
            
            # Check if bill already has a paid_amount field, if not, add it dynamically
            # For now, just update status
            old_status = bill.status
            bill.status = 'paid'
            bill.paid_date = timezone.now()
            bill.save()
            
            # Record payment in bill history (if you have such model)
            # BillPaymentHistory.objects.create(...)
            
            transaction_obj.property_bill = bill
            logger.info(f"Property bill {bill_reference} marked as paid. Status: {old_status} -> paid")
            
        elif bill_type == 'business':
            bill = BopsBills.objects.get(bill_number=bill_reference)
            old_status = bill.status
            bill.status = 'paid'
            bill.paid_date = timezone.now()
            bill.save()
            
            transaction_obj.business_bill = bill
            logger.info(f"Business bill {bill_reference} marked as paid. Status: {old_status} -> paid")
        
        transaction_obj.save()
        
        # Send confirmation asynchronously (consider using Celery)
        try:
            self.send_payment_confirmation(transaction_obj)
        except Exception as e:
            logger.error(f"Failed to send payment confirmation: {str(e)}")
    
    def _process_failed_payment(self, transaction_obj, error_message=None):
        """Process a failed payment"""
        transaction_obj.status = 'failed'
        if error_message:
            transaction_obj.error_message = error_message
        transaction_obj.save()
        logger.info(f"Payment failed: {transaction_obj.provider_transaction_id} - {error_message}")
    
    def generate_transaction_id(self) -> str:
        """Generate unique transaction ID"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_part = secrets.token_hex(4).upper()
        return f"TXN-{timestamp}-{random_part}"
    
    def send_payment_confirmation(self, transaction_obj):
        """Send payment confirmation SMS/Email"""
        try:
            # Import here to avoid circular imports
            from ..views import sendsmsView
            
            # Get contact details
            phone, name = self._get_payer_details(transaction_obj)
            
            if phone:
                message = self._format_confirmation_message(transaction_obj, name)
                
                # Send SMS
                response = sendsmsView(phone, message, "COCOAREHAB")
                
                if response.status_code == 200:
                    logger.info(f"Payment confirmation SMS sent to {phone}")
                else:
                    logger.warning(f"Failed to send SMS: {response.status_code}")
            
            # TODO: Send email confirmation if email exists
            
        except Exception as e:
            logger.exception(f"Error sending payment confirmation: {str(e)}")
            # Don't raise - confirmation sending shouldn't break the main flow
    
    def _get_payer_details(self, transaction_obj) -> Tuple[Optional[str], Optional[str]]:
        """Get payer phone and name from transaction"""
        if transaction_obj.bill_type == 'property' and transaction_obj.property_bill:
            contact = transaction_obj.property_bill.property.owners.filter(
                is_primary_owner=True
            ).first()
            return (
                contact.phone_number if contact else transaction_obj.payer_phone,
                contact.owner_name if contact else transaction_obj.payer_name
            )
        elif transaction_obj.bill_type == 'business' and transaction_obj.business_bill:
            return (
                transaction_obj.business_bill.business.phone_number or transaction_obj.payer_phone,
                transaction_obj.business_bill.business.business_name or transaction_obj.payer_name
            )
        return (transaction_obj.payer_phone, transaction_obj.payer_name)
    
    def _format_confirmation_message(self, transaction_obj, name) -> str:
        """Format payment confirmation message"""
        bill_number = self._get_bill_number(transaction_obj)
        
        return (
            f"Payment Confirmation\n"
            f"Dear {name or 'Valued Customer'},\n"
            f"Your payment of GHS {transaction_obj.amount} for bill {bill_number} "
            f"has been received successfully.\n"
            f"Transaction ID: {transaction_obj.transaction_id}\n"
            f"Date: {transaction_obj.completed_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"Thank you for your prompt payment."
        )
    
    def _get_bill_number(self, transaction_obj) -> str:
        """Get bill number from transaction"""
        if transaction_obj.property_bill:
            return transaction_obj.property_bill.bill_number
        elif transaction_obj.business_bill:
            return transaction_obj.business_bill.bill_number
        return "N/A"
    
    def verify_payment(self, provider_transaction_id: str) -> Dict[str, Any]:
        """Verify payment status with Kowri"""
        try:
            headers = self.generate_headers()
            url = f"{self.base_url}/api/v1/transactions/{provider_transaction_id}"
            
            response = requests.get(
                url,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to verify payment: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f"Failed to verify payment: {response.status_code}"
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error verifying payment: {str(e)}")
            return {
                'success': False,
                'error': f"Network error: {str(e)}"
            }
        except Exception as e:
            logger.exception(f"Unexpected error verifying payment: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }