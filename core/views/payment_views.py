# views/payment_views.py
import json
import hmac
import hashlib
import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional

from django.conf import settings
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.views.decorators.cache import never_cache
from django.core.exceptions import ValidationError

from ..services.payment_service import KowriPaymentService
from ..models import (
    PaymentProvider, PaymentTransaction, PaymentNotification,
    Bill, BopsBills, PropertyOwner
)

# Set up logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

class PaymentViewMixin:
    """Mixin with common payment view functionality"""
    
    def get_payment_service(self, provider_id: Optional[int] = None) -> KowriPaymentService:
        """Get payment service instance"""
        try:
            if provider_id:
                provider = get_object_or_404(
                    PaymentProvider, 
                    id=provider_id, 
                    is_active=True
                )
                return KowriPaymentService(provider)
            return KowriPaymentService()
        except Exception as e:
            logger.error(f"Failed to initialize payment service: {str(e)}")
            raise

    def json_response(self, success: bool = True, data: Dict = None, 
                     error: str = None, status: int = 200) -> JsonResponse:
        """Standardized JSON response"""
        response = {'success': success}
        if data:
            response.update(data)
        if error:
            response['error'] = error
        return JsonResponse(response, status=status)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def kowri_bill_lookup(request: HttpRequest) -> JsonResponse:
    """
    Endpoint for Kowri to lookup bill details
    This will be called when a payer initiates payment
    
    Expected parameters:
    - reference: Bill number or ID
    - type: 'property' or 'business' (default: 'property')
    - provider_id: Optional provider ID for multi-provider setups
    """
    view = PaymentViewMixin()
    request_id = f"lookup_{timezone.now().timestamp()}"
    
    try:
        # Log incoming request for debugging
        logger.info(f"[{request_id}] Bill lookup request: {request.method}")
        
        # Extract parameters based on request method
        if request.method == 'GET':
            bill_reference = request.GET.get('reference')
            bill_type = request.GET.get('type', 'property')
            provider_id = request.GET.get('provider_id')
        else:
            try:
                data = json.loads(request.body)
                bill_reference = data.get('reference')
                bill_type = data.get('type', 'property')
                provider_id = data.get('provider_id')
            except json.JSONDecodeError as e:
                logger.error(f"[{request_id}] Invalid JSON: {str(e)}")
                return view.json_response(
                    success=False,
                    error='Invalid JSON payload',
                    status=400
                )
        
        # Validate required parameters
        if not bill_reference:
            logger.warning(f"[{request_id}] Missing bill reference")
            return view.json_response(
                success=False,
                error='Bill reference is required',
                status=400
            )
        
        # Validate bill type
        valid_types = ['property', 'business']
        if bill_type not in valid_types:
            return view.json_response(
                success=False,
                error=f'Invalid bill type. Must be one of: {", ".join(valid_types)}',
                status=400
            )
        
        logger.info(f"[{request_id}] Looking up {bill_type} bill: {bill_reference}")
        
        # Initialize payment service
        try:
            service = view.get_payment_service(provider_id)
        except Exception as e:
            logger.error(f"[{request_id}] Service initialization failed: {str(e)}")
            return view.json_response(
                success=False,
                error='Payment service unavailable',
                status=503
            )
        
        # Look up bill
        result = service.lookup_bill(bill_reference, bill_type)
        
        # Log result
        if result.get('success'):
            logger.info(f"[{request_id}] Bill lookup successful: {bill_reference}")
        else:
            logger.warning(f"[{request_id}] Bill lookup failed: {result.get('error')}")
        
        # Return appropriate status code based on result
        status_code = 200 if result.get('success') else 404
        return JsonResponse(result, status=status_code)
        
    except Exception as e:
        logger.exception(f"[{request_id}] Unexpected error in bill lookup: {str(e)}")
        return view.json_response(
            success=False,
            error='An unexpected error occurred',
            status=500
        )


@csrf_exempt
@require_http_methods(["POST"])
def kowri_payment_notification(request: HttpRequest) -> JsonResponse:
    """
    Endpoint for Kowri to send payment notifications
    This is the webhook that Kowri will call after payment
    
    Expected payload structure (adjust based on Kowri's actual format):
    {
        "transaction_id": "KOWRI-TXN-123456",
        "bill_reference": "BILL-2024-000001",
        "bill_type": "property",
        "amount": "150.00",
        "status": "completed",
        "payment_method": "mobile_money",
        "channel": "USSD",
        "payer": {
            "name": "John Doe",
            "phone": "233XXXXXXXXX",
            "email": "john@example.com"
        },
        "timestamp": "2024-01-15T10:30:00Z"
    }
    """
    view = PaymentViewMixin()
    request_id = f"notify_{timezone.now().timestamp()}"
    
    try:
        # Log raw request for debugging
        logger.info(f"[{request_id}] Payment notification received")
        
        # Verify webhook signature if provided
        signature = request.headers.get('X-Kowri-Signature')
        if signature:
            if not verify_webhook_signature(request.body, signature):
                logger.warning(f"[{request_id}] Invalid webhook signature")
                return view.json_response(
                    success=False,
                    error='Invalid signature',
                    status=401
                )
        
        # Parse JSON payload
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            logger.error(f"[{request_id}] Invalid JSON payload: {str(e)}")
            return view.json_response(
                success=False,
                error='Invalid JSON payload',
                status=400
            )
        
        # Log notification data (excluding sensitive info)
        log_data = {k: v for k, v in data.items() if k != 'payer'}
        logger.info(f"[{request_id}] Processing notification: {log_data}")
        
        # Validate required fields
        required_fields = ['transaction_id', 'bill_reference', 'amount']
        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            logger.warning(f"[{request_id}] Missing required fields: {missing_fields}")
            return view.json_response(
                success=False,
                error=f'Missing required fields: {", ".join(missing_fields)}',
                status=400
            )
        
        # Validate amount
        try:
            amount = Decimal(str(data['amount']))
            if amount <= 0:
                return view.json_response(
                    success=False,
                    error='Amount must be positive',
                    status=400
                )
        except (InvalidOperation, TypeError, ValueError):
            return view.json_response(
                success=False,
                error='Invalid amount format',
                status=400
            )
        
        # Initialize payment service
        try:
            provider_id = data.get('provider_id')
            service = view.get_payment_service(provider_id)
        except Exception as e:
            logger.error(f"[{request_id}] Service initialization failed: {str(e)}")
            return view.json_response(
                success=False,
                error='Payment service unavailable',
                status=503
            )
        
        # Process payment notification
        result = service.process_payment_notification(data)
        
        # Log result
        if result.get('success'):
            logger.info(f"[{request_id}] Payment processed successfully: {result.get('transaction_id')}")
            return view.json_response(
                success=True,
                data={
                    'message': 'Payment processed successfully',
                    'transaction_id': result.get('transaction_id'),
                    'status': result.get('status')
                }
            )
        else:
            logger.error(f"[{request_id}] Payment processing failed: {result.get('error')}")
            return view.json_response(
                success=False,
                error=result.get('error', 'Payment processing failed'),
                status=400
            )
            
    except Exception as e:
        logger.exception(f"[{request_id}] Unexpected error processing notification: {str(e)}")
        return view.json_response(
            success=False,
            error='An unexpected error occurred',
            status=500
        )


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Verify webhook signature from Kowri"""
    try:
        # Get webhook secret from settings or database
        # This should be stored securely
        webhook_secret = settings.KOWRI_WEBHOOK_SECRET
        
        # Compute expected signature
        expected = hmac.new(
            webhook_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures (constant-time comparison to prevent timing attacks)
        return hmac.compare_digest(signature, expected)
        
    except Exception as e:
        logger.error(f"Signature verification failed: {str(e)}")
        return False


@login_required
@require_http_methods(["GET"])
def get_payment_status(request: HttpRequest, bill_id: int, 
                       bill_type: str = 'property') -> JsonResponse:
    """
    Get payment status for a specific bill
    Accessible to authenticated users only
    """
    view = PaymentViewMixin()
    
    try:
        # Validate bill type
        if bill_type not in ['property', 'business']:
            return view.json_response(
                success=False,
                error='Invalid bill type',
                status=400
            )
        
        # Get bill based on type
        if bill_type == 'property':
            bill = get_object_or_404(Bill, id=bill_id)
            transactions = PaymentTransaction.objects.filter(
                property_bill=bill
            ).order_by('-initiated_at')
            
            # Get bill details
            bill_info = {
                'bill_number': bill.bill_number,
                'total_amount': str(bill.total_amount),
                'status': bill.status,
                'due_date': bill.due_date,
                'paid_date': bill.paid_date
            }
        else:
            bill = get_object_or_404(BopsBills, id=bill_id)
            transactions = PaymentTransaction.objects.filter(
                business_bill=bill
            ).order_by('-initiated_at')
            
            bill_info = {
                'bill_number': bill.bill_number,
                'total_amount': str(bill.total_amount),
                'status': bill.status,
                'due_date': bill.due_date,
                'paid_date': bill.paid_date
            }
        
        # Get the most recent transaction
        transaction = transactions.first()
        
        if transaction:
            # Get payment details
            payment_info = {
                'status': transaction.status,
                'amount': str(transaction.amount),
                'transaction_id': transaction.transaction_id,
                'provider_transaction_id': transaction.provider_transaction_id,
                'payment_date': transaction.completed_at,
                'payment_method': transaction.payment_method,
                'payment_channel': transaction.payment_channel,
                'payer_name': transaction.payer_name,
                'initiated_at': transaction.initiated_at
            }
            
            # Get all payments for this bill (if multiple partial payments)
            all_payments = list(transactions.filter(
                status='completed'
            ).values('amount', 'completed_at', 'payment_method'))
            
            total_paid = sum(Decimal(str(p['amount'])) for p in all_payments) if all_payments else Decimal('0')
            balance_due = bill.total_amount - total_paid
            
            response_data = {
                'success': True,
                'bill': bill_info,
                'latest_payment': payment_info,
                'all_payments': all_payments,
                'total_paid': str(total_paid),
                'balance_due': str(balance_due),
                'is_fully_paid': balance_due <= 0
            }
        else:
            response_data = {
                'success': True,
                'bill': bill_info,
                'status': 'not_paid',
                'message': 'No payment found for this bill'
            }
        
        return view.json_response(success=True, data=response_data)
            
    except Bill.DoesNotExist:
        return view.json_response(
            success=False,
            error='Property bill not found',
            status=404
        )
    except BopsBills.DoesNotExist:
        return view.json_response(
            success=False,
            error='Business bill not found',
            status=404
        )
    except Exception as e:
        logger.exception(f"Error getting payment status: {str(e)}")
        return view.json_response(
            success=False,
            error=str(e),
            status=500
        )


@login_required
@require_http_methods(["GET"])
@never_cache
def list_payment_transactions(request: HttpRequest) -> JsonResponse:
    """
    List payment transactions with pagination and filtering
    Accessible to authenticated users only (admin view)
    
    Query parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 50, max: 200)
    - status: Filter by status (pending, completed, failed, refunded)
    - bill_type: Filter by bill type (property, business)
    - date_from: Start date (YYYY-MM-DD)
    - date_to: End date (YYYY-MM-DD)
    - search: Search by transaction ID, bill number, or payer name
    """
    view = PaymentViewMixin()
    
    try:
        # Get query parameters
        page = int(request.GET.get('page', 1))
        page_size = min(int(request.GET.get('page_size', DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
        status_filter = request.GET.get('status')
        bill_type_filter = request.GET.get('bill_type')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        search_query = request.GET.get('search', '').strip()
        
        # Base queryset
        transactions = PaymentTransaction.objects.select_related(
            'provider', 'property_bill', 'business_bill',
            'property_bill__property', 'business_bill__business'
        ).order_by('-initiated_at')
        
        # Apply filters
        if status_filter:
            transactions = transactions.filter(status=status_filter)
        
        if bill_type_filter and bill_type_filter in ['property', 'business']:
            if bill_type_filter == 'property':
                transactions = transactions.filter(property_bill__isnull=False)
            else:
                transactions = transactions.filter(business_bill__isnull=False)
        
        if date_from:
            transactions = transactions.filter(initiated_at__date__gte=date_from)
        
        if date_to:
            transactions = transactions.filter(initiated_at__date__lte=date_to)
        
        if search_query:
            transactions = transactions.filter(
                Q(transaction_id__icontains=search_query) |
                Q(provider_transaction_id__icontains=search_query) |
                Q(property_bill__bill_number__icontains=search_query) |
                Q(business_bill__bill_number__icontains=search_query) |
                Q(payer_name__icontains=search_query) |
                Q(payer_phone__icontains=search_query)
            )
        
        # Get summary statistics
        summary = transactions.aggregate(
            total_count=Count('id'),
            total_amount=Sum('amount', filter=Q(status='completed')),
            pending_count=Count('id', filter=Q(status='pending')),
            completed_count=Count('id', filter=Q(status='completed')),
            failed_count=Count('id', filter=Q(status='failed'))
        )
        
        # Paginate
        paginator = Paginator(transactions, page_size)
        current_page = paginator.get_page(page)
        
        # Format transaction data
        data = []
        for t in current_page.object_list:
            transaction_data = format_transaction_data(t)
            data.append(transaction_data)
        
        # Prepare response
        response_data = {
            'success': True,
            'transactions': data,
            'pagination': {
                'current_page': current_page.number,
                'total_pages': paginator.num_pages,
                'total_records': paginator.count,
                'page_size': page_size,
                'has_next': current_page.has_next(),
                'has_previous': current_page.has_previous()
            },
            'summary': {
                'total_count': summary['total_count'],
                'total_amount': str(summary['total_amount'] or 0),
                'pending_count': summary['pending_count'],
                'completed_count': summary['completed_count'],
                'failed_count': summary['failed_count']
            }
        }
        
        return view.json_response(success=True, data=response_data)
        
    except ValueError as e:
        return view.json_response(
            success=False,
            error=f'Invalid parameter: {str(e)}',
            status=400
        )
    except Exception as e:
        logger.exception(f"Error listing transactions: {str(e)}")
        return view.json_response(
            success=False,
            error=str(e),
            status=500
        )


def format_transaction_data(transaction: PaymentTransaction) -> Dict[str, Any]:
    """Format transaction data for API response"""
    # Get bill information
    bill_info = {}
    if transaction.property_bill:
        bill_info = {
            'bill_number': transaction.property_bill.bill_number,
            'bill_type_display': 'Property Tax',
            'bill_type': 'property',
            'reference': {
                'property_id': transaction.property_bill.property.id,
                'property_address': transaction.property_bill.property.address,
                'zone': transaction.property_bill.property.zone.name if transaction.property_bill.property.zone else None
            }
        }
    elif transaction.business_bill:
        bill_info = {
            'bill_number': transaction.business_bill.bill_number,
            'bill_type_display': 'Business Permit',
            'bill_type': 'business',
            'reference': {
                'business_id': transaction.business_bill.business.id,
                'business_name': transaction.business_bill.business.business_name,
                'account_number': transaction.business_bill.business.account_number
            }
        }
    
    return {
        'id': transaction.id,
        'transaction_id': transaction.transaction_id,
        'provider_transaction_id': transaction.provider_transaction_id,
        'amount': str(transaction.amount),
        'status': transaction.status,
        'status_display': transaction.get_status_display(),
        'payment_method': transaction.payment_method,
        'payment_channel': transaction.payment_channel,
        'payer': {
            'name': transaction.payer_name,
            'phone': transaction.payer_phone,
            'email': transaction.payer_email
        },
        'provider': {
            'id': transaction.provider.id,
            'name': transaction.provider.name
        },
        'bill': bill_info,
        'timestamps': {
            'initiated': transaction.initiated_at,
            'completed': transaction.completed_at
        },
        'metadata': transaction.metadata
    }


@login_required
@require_http_methods(["GET"])
def get_transaction_detail(request: HttpRequest, transaction_id: str) -> JsonResponse:
    """
    Get detailed information about a specific transaction
    """
    view = PaymentViewMixin()
    
    try:
        # Get transaction by ID or transaction_id
        transaction = get_object_or_404(
            PaymentTransaction,
            Q(id=transaction_id) | Q(transaction_id=transaction_id)
        )
        
        # Get associated notifications
        notifications = transaction.notifications.all().order_by('-created_at')
        
        # Format transaction data
        transaction_data = format_transaction_data(transaction)
        
        # Add notifications
        transaction_data['notifications'] = [
            {
                'id': n.id,
                'processed': n.processed,
                'error': n.error,
                'created_at': n.created_at,
                'raw_data': n.raw_data  # Consider redacting sensitive data
            }
            for n in notifications
        ]
        
        return view.json_response(
            success=True,
            data={'transaction': transaction_data}
        )
        
    except Exception as e:
        logger.exception(f"Error getting transaction detail: {str(e)}")
        return view.json_response(
            success=False,
            error=str(e),
            status=500
        )


@login_required
@require_http_methods(["GET"])
def get_payment_providers(request: HttpRequest) -> JsonResponse:
    """
    Get list of active payment providers
    """
    view = PaymentViewMixin()
    
    try:
        providers = PaymentProvider.objects.filter(is_active=True).values(
            'id', 'name', 'provider_type'
        )
        
        return view.json_response(
            success=True,
            data={'providers': list(providers)}
        )
        
    except Exception as e:
        logger.exception(f"Error getting providers: {str(e)}")
        return view.json_response(
            success=False,
            error=str(e),
            status=500
        )


@login_required
@require_http_methods(["POST"])
def retry_failed_notification(request: HttpRequest, notification_id: int) -> JsonResponse:
    """
    Retry processing a failed notification (admin only)
    """
    view = PaymentViewMixin()
    
    # Check if user has admin permissions
    if not request.user.is_staff:
        return view.json_response(
            success=False,
            error='Permission denied',
            status=403
        )
    
    try:
        notification = get_object_or_404(PaymentNotification, id=notification_id)
        
        if notification.processed:
            return view.json_response(
                success=False,
                error='Notification already processed',
                status=400
            )
        
        # Initialize service and reprocess
        service = view.get_payment_service()
        result = service.process_payment_notification(notification.raw_data)
        
        if result.get('success'):
            return view.json_response(
                success=True,
                data={'message': 'Notification reprocessed successfully'}
            )
        else:
            return view.json_response(
                success=False,
                error=result.get('error', 'Reprocessing failed'),
                status=400
            )
            
    except Exception as e:
        logger.exception(f"Error retrying notification: {str(e)}")
        return view.json_response(
            success=False,
            error=str(e),
            status=500
        )