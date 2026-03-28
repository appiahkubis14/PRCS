# core/views/payment_views.py
import json
import hmac
import hashlib
import logging
import urllib.parse
import requests
import traceback
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from django.conf import settings
from django.http import JsonResponse, HttpRequest, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.views.decorators.cache import never_cache

from ..models import (
    PaymentProvider, PaymentTransaction, PaymentNotification,
    BopsBills, PaymentLinkClick, Bops,
)

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE     = 200


# ===========================================================================
# Helpers
# ===========================================================================

def _get_client_ip(request: HttpRequest) -> str:
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def get_tracked_payment_link(bill_type: str, bill_number: str, link_type: str = 'web') -> str:
    """Return a redirect URL that tracks the click before forwarding to the payment page."""
    base_url = getattr(settings, 'BASE_URL', 'http://192.168.3.15:8000/').rstrip('/')
    return f"{base_url}/pay/l/{bill_type}/{bill_number}/{link_type}/"


# ===========================================================================
# SMS helpers
# ===========================================================================

def send_sms(contact: str, message: str, sender: str = "COCOAREHAB"):
    """
    Send an SMS via SMSOnlineGH.
    Returns (success: bool, response_data: dict | str).
    """
    try:
        api_key         = getattr(settings, 'SMS_API_KEY', 'cc37ca2903ecf3cf5d6ea90026d45a20b12dd20853c099839be7c68549f4a322')
        encoded_message = urllib.parse.quote_plus(message)
        url = (
            f"https://api.smsonlinegh.com/v4/message/sms/send"
            f"?key={api_key}&text={encoded_message}&type=0&sender={sender}&to={contact}"
        )
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        logger.info(f"SMS sent to {contact}: status {response.status_code}")
        return True, response.json() if response.text else {}
    except requests.exceptions.RequestException as exc:
        logger.error(f"SMS request error for {contact}: {exc}")
        return False, str(exc)
    except Exception as exc:
        logger.error(f"Unexpected SMS error for {contact}: {exc}")
        return False, str(exc)


def build_bops_sms(bill: 'BopsBills') -> str:
    """Build the billing SMS body for a BopsBills instance."""
    web_link      = get_tracked_payment_link('business', bill.bill_number, 'web')
    ussd_code     = f"*227*130*{bill.bill_number}#"
    due_date_str  = bill.due_date.strftime('%d %B, %Y') if bill.due_date else 'N/A'
    business_name = bill.business.business_name

    return (
        f"Dear {business_name},\n\n"
        f"Your Business Operating Permit (BOP) bill for {bill.billing_year} "
        f"of GH\u20b5{bill.total_amount:,.2f} is due on {due_date_str}.\n\n"
        f"\U0001f517 Quick Pay Online: {web_link}\n"
        f"\U0001f4f1 USSD: {ussd_code}\n\n"
        f"Please pay before the due date to avoid penalties.\n\n"
        f"COCOAREHAB Revenue Collection"
    )


def send_bops_billing_sms(bill: 'BopsBills') -> tuple:
    """Send the billing SMS for a single BopsBills. Returns (success, result)."""
    contact = (
        getattr(bill.business, 'phone_number_primary', None)
        or getattr(bill.business, 'phone_number', None)
        or ''
    )
    if not contact:
        logger.warning(
            f"No phone number for business {bill.business.business_name} (bill {bill.bill_number})"
        )
        return False, "No phone number on record"
    return send_sms(contact, build_bops_sms(bill))


# ===========================================================================
# PaymentViewMixin
# ===========================================================================

class PaymentViewMixin:
    """Mixin with common payment view functionality."""

    def get_payment_service(self, provider_id: Optional[int] = None):
        try:
            from ..services.payment_service import KowriPaymentService
            if provider_id:
                provider = get_object_or_404(PaymentProvider, id=provider_id, is_active=True)
                return KowriPaymentService(provider)
            return KowriPaymentService()
        except Exception as exc:
            logger.error(f"Failed to initialise payment service: {exc}")
            raise

    @staticmethod
    def json_response(success: bool = True, data: Dict = None,
                      error: str = None, status: int = 200) -> JsonResponse:
        body = {'success': success}
        if data:
            body.update(data)
        if error:
            body['error'] = error
        return JsonResponse(body, status=status)


# ===========================================================================
# Bops bill list / management pages
# ===========================================================================

def bop_easy_collectible_list(request):
    """Display BopsBills as receipt cards (newbop.html template)."""
    try:
        billing_year = request.GET.get('billing_year', timezone.now().year)
        block        = request.GET.get('block', '').strip()
        division     = request.GET.get('division', '').strip()
        business_ids = request.GET.get('business_ids', '')
        bill_id      = request.GET.get('bill_id', '').strip()
        download     = request.GET.get('download', '').strip()

        try:
            billing_year = int(billing_year)
        except (ValueError, TypeError):
            billing_year = timezone.now().year

        if bill_id:
            try:
                qs = BopsBills.objects.filter(id=int(bill_id), ).select_related('business')
            except (ValueError, TypeError):
                qs = BopsBills.objects.none()
        else:
            qs = BopsBills.objects.filter(billing_year=billing_year, ).select_related('business')
            if block:
                qs = qs.filter(business__block=block)
            if division:
                qs = qs.filter(business__division=division)
            if business_ids:
                try:
                    id_list = [int(i.strip()) for i in business_ids.split(',') if i.strip()]
                    if id_list:
                        qs = qs.filter(business__id__in=id_list)
                except (ValueError, TypeError):
                    pass

        qs = qs.order_by('bill_number')

        return render(request, 'core/main/billing/newbop.html', {
            'bop_easy_collectibles': qs,
            'billing_year': billing_year,
            'auto_download': bool(download),
        })

    except Exception as exc:
        logger.exception(f"Error loading bills: {exc}")
        return render(request, 'core/main/billing/bopbill.html', {
            'bop_easy_collectibles': [],
            'billing_year': timezone.now().year,
            'error': str(exc),
        })


def bops_bills_list_page(request):
    """Render the BopsBills management list page."""
    return render(request, 'core/main/billing/bops-bills-list.html', {
        'page_title': 'BOP Bills Management',
        'active_menu': 'bops_bills',
    })


def bops_bill_receipt(request, bill_id):
    """Render the BOP bill receipt for a single bill."""
    bill = get_object_or_404(
        BopsBills.objects.all().select_related('business'),
        id=bill_id,
    )
    return render(request, 'core/main/billing/newbop.html', {
        'bop_easy_collectibles': [bill],
        'billing_year': bill.billing_year,
    })


# ===========================================================================
# Bops / BopsBills filter helpers
# ===========================================================================

@require_http_methods(["GET"])
def get_bops_list(request):
    """Get all Bops businesses for dropdown / Select2."""
    try:
        search = request.GET.get('search', '').strip()
        qs     = Bops.objects.all()

        if search:
            qs = qs.filter(
                Q(account_number__icontains=search) |
                Q(business_name__icontains=search) |
                Q(owner_name__icontains=search) |
                Q(location__icontains=search) |
                Q(block__icontains=search) |
                Q(division__icontains=search)
            )

        data = []
        for bop in qs:
            business_name  = bop.business_name or 'Unnamed Business'
            account_number = bop.account_number or 'N/A'
            data.append({
                'id': bop.id,
                'account_number': account_number,
                'business_name': business_name,
                'owner_name': bop.owner_name or '',
                'location': bop.location or '',
                'block': getattr(bop, 'block', '') or '',
                'division': getattr(bop, 'division', '') or '',
                'display_text': f"{account_number} - {business_name}",
            })

        return JsonResponse({'success': True, 'bops': data, 'total': len(data)})
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)


@require_http_methods(["GET"])
def get_billing_years(request):
    """Get distinct billing years that have BopsBills."""
    try:
        current_year = timezone.now().year
        try:
            years = list(
                BopsBills.objects.all()
                .values_list('billing_year', flat=True)
                .distinct()
            )
        except Exception:
            years = []

        years = sorted(set(years + [current_year, current_year + 1]), reverse=True)
        return JsonResponse({'success': True, 'years': years})
    except Exception:
        current_year = timezone.now().year
        return JsonResponse({'success': True, 'years': [current_year + 1, current_year]})


@require_http_methods(["GET"])
def get_bops_blocks(request):
    """Get distinct blocks from Bops."""
    try:
        blocks = (
            Bops.objects.all()
            .values_list('block', flat=True)
            .distinct()
            .order_by('block')
        )
        blocks_list = sorted({b.strip() for b in blocks if b and str(b).strip()})
        return JsonResponse({'success': True, 'blocks': blocks_list})
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)


@require_http_methods(["GET"])
def get_bops_divisions(request):
    """Get distinct divisions from Bops (optionally filtered by block)."""
    try:
        block = request.GET.get('block', '').strip()
        qs    = Bops.objects.all().exclude(division__isnull=True).exclude(division__exact='')
        if block:
            qs = qs.filter(block=block)
        divisions = sorted({d.strip() for d in qs.values_list('division', flat=True).distinct() if d and d.strip()})
        return JsonResponse({'success': True, 'divisions': divisions})
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)


@require_http_methods(["GET"])
def get_bops_blocks_by_division(request):
    """Get distinct blocks for a given division."""
    try:
        division = request.GET.get('division', '').strip()
        qs       = Bops.objects.all().exclude(block__isnull=True).exclude(block__exact='')
        if division:
            qs = qs.filter(division__iexact=division)
        blocks = sorted({b.strip() for b in qs.values_list('block', flat=True).distinct() if b and b.strip()})
        return JsonResponse({'success': True, 'blocks': blocks})
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)


@require_http_methods(["GET"])
def get_bops_bills_list(request):
    """Get all BopsBills for DataTable."""
    try:
        draw         = int(request.GET.get('draw', 1))
        search_value = request.GET.get('search[value]', '')
        order_column = int(request.GET.get('order[0][column]', 0))
        order_dir    = request.GET.get('order[0][dir]', 'asc')

        qs = BopsBills.objects.all().select_related('business')

        if search_value:
            qs = qs.filter(
                Q(bill_number__icontains=search_value) |
                Q(business__business_name__icontains=search_value) |
                Q(business__account_number__icontains=search_value) |
                Q(business__owner_name__icontains=search_value) |
                Q(status__icontains=search_value)
            )

        total_records = qs.count()

        column_map = {
            1: 'bill_number',           2: 'business__business_name',
            3: 'business__account_number', 4: 'business__owner_name',
            5: 'billing_year',          6: 'tax_amount',
            7: 'penalty_amount',        8: 'discount_amount',
            9: 'total_amount',          10: 'status',
            11: 'generated_date',       12: 'due_date',
        }
        order_field = column_map.get(order_column, 'id')
        if order_dir == 'desc':
            order_field = f'-{order_field}'
        qs = qs.order_by(order_field)

        data = [{
            'id':             b.id,
            'bill_number':    b.bill_number,
            'business_name':  b.business.business_name or '',
            'account_number': b.business.account_number or '',
            'owner_name':     b.business.owner_name or '',
            'billing_year':   b.billing_year,
            'tax_amount':     str(b.tax_amount),
            'penalty_amount': str(b.penalty_amount),
            'discount_amount':str(b.discount_amount),
            'total_amount':   str(b.total_amount),
            'status':         b.status,
            'generated_date': b.issued_at.strftime('%Y-%m-%d %H:%M') if b.issued_at else '',
            'due_date':       b.due_date.strftime('%Y-%m-%d') if b.due_date else '',
            'business_id':    b.business.id,
        } for b in qs]

        return JsonResponse({'draw': draw, 'recordsTotal': total_records,
                             'recordsFiltered': total_records, 'data': data})
    except Exception as exc:
        logger.exception(exc)
        return JsonResponse({'draw': int(request.GET.get('draw', 1)),
                             'recordsTotal': 0, 'recordsFiltered': 0,
                             'data': [], 'error': str(exc)}, status=500)


# ===========================================================================
# Bops bill generation with auto-SMS
# ===========================================================================

@csrf_exempt
@require_http_methods(["POST"])
def generate_bops_bills(request: HttpRequest) -> JsonResponse:
    print("generate_bops_bills called with body:", request.body)
    """
    Generate BopsBills for selected businesses.
    Auto-sends billing SMS after each new bill is committed.
    """
    view = PaymentViewMixin()

    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as exc:
            return view.json_response(False, error=f'Invalid JSON: {exc}', status=400)

        business_ids    = data.get('business_ids', [])
        billing_year    = data.get('billing_year')
        tax_amount      = data.get('tax_amount', 0)
        penalty_amount  = data.get('penalty_amount', 0)
        discount_amount = data.get('discount_amount', 0)
        due_date_str    = data.get('due_date')
        notes           = data.get('notes', '')
        
        print(f"Parsed input - business_ids: {business_ids}, billing_year: {billing_year}, "
              f"tax_amount: {tax_amount}, penalty_amount: {penalty_amount}, "
              f"discount_amount: {discount_amount}, due_date_str: {due_date_str}, notes: {notes}")

        if not business_ids or not isinstance(business_ids, list):
            return view.json_response(False, error='business_ids must be a non-empty list', status=400)
        if not billing_year:
            return view.json_response(False, error='billing_year is required', status=400)
        try:
            billing_year = int(billing_year)
        except (ValueError, TypeError):
            return view.json_response(False, error='billing_year must be an integer', status=400)

        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                return view.json_response(False, error='Invalid due_date. Expected YYYY-MM-DD', status=400)
        else:
            due_date = datetime.now().date() + timedelta(days=30)

        generated_bills, errors = [], []

        for business_id in business_ids:
            try:
                with transaction.atomic():
                    try:
                        business = Bops.objects.get(id=business_id, )
                    except Bops.DoesNotExist:
                        errors.append(f"Business ID {business_id} not found")
                        continue
                        
                    existing = BopsBills.objects.filter(
                        business=business,
                        billing_year=billing_year,
                        
                    ).exclude(status='cancelled').first()

                    if existing:
                        generated_bills.append({
                            'id':            existing.id,
                            'bill_number':   existing.bill_number,
                            'business_name': business.business_name,
                            'account_number':business.account_number,
                            'total_amount':  str(existing.total_amount),
                            'existing':      True,
                            'sms_sent':      False,
                            'sms_note':      'Bill already existed; SMS not re-sent',
                        })
                        continue

                    try:
                        bill_tax   = float(tax_amount) if tax_amount and float(tax_amount) > 0 \
                                     else float(business.flat_rate or 0)
                        bill_total = bill_tax - float(discount_amount) + float(penalty_amount)
                        if bill_total < 0:
                            errors.append(
                                f"Negative total for {business.business_name}: "
                                f"tax={bill_tax}, discount={discount_amount}, penalty={penalty_amount}"
                            )
                            continue
                    except (ValueError, TypeError) as exc:
                        errors.append(f"Amount error for {business.business_name}: {exc}")
                        continue

                    bill = BopsBills.objects.create(
                        business=business,
                        billing_year=billing_year,
                        tax_amount=bill_tax,
                        penalty_amount=float(penalty_amount),
                        discount_amount=float(discount_amount),
                        total_amount=bill_total,
                        due_date=due_date,
                        status='generated',
                        notes=notes,
                        added_by=request.user if request.user.is_authenticated else None,
                    )

                # SMS outside atomic so the row is committed first
                print(f"Sending SMS for bill {bill.bill_number}")
                sms_ok, sms_result = send_bops_billing_sms(bill)
                print(f"SMS result for {bill.bill_number}: {sms_result}")
                if sms_ok:
                    BopsBills.objects.filter(pk=bill.pk).update(
                        status='sent',
                        sent_date=timezone.now(),
                    )

                generated_bills.append({
                    'id':            bill.id,
                    'bill_number':   bill.bill_number,
                    'business_name': business.business_name,
                    'account_number':business.account_number,
                    'total_amount':  str(bill.total_amount),
                    'existing':      False,
                    'sms_sent':      sms_ok,
                    'sms_result':    sms_result if not sms_ok else 'OK',
                })

            except Exception as exc:
                logger.error(f"Error processing business ID {business_id}:\n{traceback.format_exc()}")
                errors.append(f"Error for business ID {business_id}: {exc}")

        if generated_bills:
            return view.json_response(True, data={
                'message': f'Processed {len(generated_bills)} bill(s)',
                'bills':   generated_bills,
                'errors':  errors or None,
            })
        return view.json_response(False, error='No bills were generated', status=400,
                                  data={'errors': errors})

    except Exception as exc:
        logger.exception(f"Unexpected error in generate_bops_bills: {exc}")
        return view.json_response(False, error=str(exc), status=500)


@csrf_exempt
@require_http_methods(["POST"])
def regenerate_bops_bill(request, bill_id):
    """Regenerate (re-activate) a specific BopsBill."""
    try:
        bill = BopsBills.objects.get(id=bill_id, )

        conflict = BopsBills.objects.filter(
            business=bill.business,
            billing_year=bill.billing_year,
            
        ).exclude(id=bill_id).exclude(status='cancelled').first()

        if conflict:
            return JsonResponse({'success': False,
                                 'error': f'Duplicate bill exists: {conflict.bill_number}'}, status=400)

        bill.status = 'generated'
        bill.save()
        return JsonResponse({'success': True,
                             'message': f'Bill {bill.bill_number} regenerated',
                             'bill_number': bill.bill_number})

    except BopsBills.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Bill not found'}, status=404)
    except Exception as exc:
        logger.exception(exc)
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def send_bops_bill_message(request, bill_id):
    """Send (or re-send) the billing SMS for a specific BopsBill."""
    try:
        bill    = BopsBills.objects.get(id=bill_id, )
        ok, res = send_bops_billing_sms(bill)

        if ok:
            BopsBills.objects.filter(pk=bill.pk).update(
                status='sent',
                sent_date=timezone.now(),
            )
            return JsonResponse({
                'success':      True,
                'message':      f'Message sent for bill {bill.bill_number}',
                'bill_number':  bill.bill_number,
                'tracked_link': get_tracked_payment_link('business', bill.bill_number, 'web'),
            })

        return JsonResponse({'success': False, 'error': f'SMS failed: {res}'}, status=502)

    except BopsBills.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Bill not found'}, status=404)
    except Exception as exc:
        logger.exception(exc)
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)


# ===========================================================================
# Payment-link click tracking
# ===========================================================================

@csrf_exempt
@require_http_methods(["POST"])
def track_payment_link_click(request: HttpRequest) -> JsonResponse:
    """
    Record a click on a payment link.
    POST body JSON: { bill_type: 'business', bill_id: int, link_type: str }
    """
    view = PaymentViewMixin()
    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return view.json_response(False, error='Invalid JSON', status=400)

        bill_type = data.get('bill_type')
        bill_id   = data.get('bill_id')
        link_type = data.get('link_type', 'web')

        if not bill_type or not bill_id:
            return view.json_response(False, error='bill_type and bill_id are required', status=400)

        valid_link_types = [lt[0] for lt in PaymentLinkClick.LINK_TYPES]
        if link_type not in valid_link_types:
            return view.json_response(
                False,
                error=f'Invalid link_type. Must be one of: {", ".join(valid_link_types)}',
                status=400,
            )

        if bill_type != 'business':
            return view.json_response(False, error="Only bill_type 'business' is supported", status=400)

        bill  = get_object_or_404(BopsBills, id=bill_id, )
        click = _record_click(bill, link_type, request)

        return view.json_response(True, data={
            'message':     'Click tracked',
            'click_id':    click.id,
            'click_count': bill.click_count,
        })

    except Exception as exc:
        logger.exception(f"Error tracking click: {exc}")
        return view.json_response(False, error=str(exc), status=500)


def payment_link_redirect(request: HttpRequest, bill_type: str,
                          bill_number: str, link_type: str = 'web') -> HttpResponseRedirect:
    """
    Track click then redirect to the Kowri payment page.
    URL: /pay/l/<bill_type>/<bill_number>/<link_type>/
    """
    try:
        if bill_type != 'bops' or bill_type != 'business':
            return HttpResponseRedirect('/')

        bill         = get_object_or_404(BopsBills, bill_number=bill_number, )
        redirect_url = f"https://collections.kowri.app/130/{bill_number}"

        _record_click(bill, link_type, request)
        return HttpResponseRedirect(redirect_url)

    except Exception as exc:
        logger.error(f"Error in payment_link_redirect: {exc}")
        return HttpResponseRedirect('/')


def _record_click(bill: 'BopsBills', link_type: str, request: HttpRequest) -> PaymentLinkClick:
    """Create a PaymentLinkClick and update the bill's click counters."""
    ip_address = _get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    referer    = request.META.get('HTTP_REFERER', '')[:500]
    session_id = ''
    if hasattr(request, 'session') and request.session.session_key:
        session_id = request.session.session_key

    click = PaymentLinkClick.objects.create(
        business_bill=bill,
        bill_type='business',
        link_type=link_type,
        ip_address=ip_address or None,
        user_agent=user_agent,
        referer=referer,
        session_id=session_id,
    )

    bill.last_clicked_at = click.clicked_at
    bill.click_count     = (bill.click_count or 0) + 1
    bill.last_click_ip   = ip_address or None
    bill.save(update_fields=['last_clicked_at', 'click_count', 'last_click_ip'])

    return click


# ===========================================================================
# Webhook signature verification
# ===========================================================================

def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Verify the HMAC-SHA256 signature on an incoming Kowri webhook."""
    try:
        webhook_secret = getattr(settings, 'KOWRI_WEBHOOK_SECRET', '')
        if not webhook_secret:
            logger.warning("KOWRI_WEBHOOK_SECRET not configured; skipping signature check")
            return True
        expected = hmac.new(webhook_secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    except Exception as exc:
        logger.error(f"Signature verification error: {exc}")
        return False


# ===========================================================================
# Kowri integration
# ===========================================================================

@csrf_exempt
@require_http_methods(["GET", "POST"])
def kowri_bill_lookup(request: HttpRequest) -> JsonResponse:
    """Kowri calls this to look up bill details before initiating payment."""
    view       = PaymentViewMixin()
    request_id = f"lookup_{timezone.now().timestamp()}"

    try:
        if request.method == 'GET':
            bill_reference = request.GET.get('reference')
            provider_id    = request.GET.get('provider_id')
        else:
            try:
                payload = json.loads(request.body)
            except json.JSONDecodeError:
                return view.json_response(False, error='Invalid JSON', status=400)
            bill_reference = payload.get('reference')
            provider_id    = payload.get('provider_id')

        if not bill_reference:
            return view.json_response(False, error='reference is required', status=400)

        try:
            service = view.get_payment_service(provider_id)
        except Exception as exc:
            logger.error(f"[{request_id}] Service init failed: {exc}")
            return view.json_response(False, error='Payment service unavailable', status=503)

        result = service.lookup_bill(bill_reference, 'business')
        return JsonResponse(result, status=200 if result.get('success') else 404)

    except Exception as exc:
        logger.exception(f"[{request_id}] Unexpected error in bill lookup: {exc}")
        return view.json_response(False, error='Unexpected error', status=500)


@csrf_exempt
@require_http_methods(["POST"])
def kowri_payment_notification(request: HttpRequest) -> JsonResponse:
    """Kowri calls this webhook after a payment is processed."""
    view       = PaymentViewMixin()
    request_id = f"notify_{timezone.now().timestamp()}"

    try:
        signature = request.headers.get('X-Kowri-Signature')
        if signature and not verify_webhook_signature(request.body, signature):
            logger.warning(f"[{request_id}] Invalid webhook signature")
            return view.json_response(False, error='Invalid signature', status=401)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return view.json_response(False, error='Invalid JSON', status=400)

        required = ['transaction_id', 'bill_reference', 'amount']
        missing  = [f for f in required if f not in data]
        if missing:
            return view.json_response(False, error=f'Missing fields: {", ".join(missing)}', status=400)

        try:
            amount = Decimal(str(data['amount']))
            if amount <= 0:
                return view.json_response(False, error='Amount must be positive', status=400)
        except (InvalidOperation, TypeError, ValueError):
            return view.json_response(False, error='Invalid amount', status=400)

        try:
            service = view.get_payment_service(data.get('provider_id'))
        except Exception as exc:
            logger.error(f"[{request_id}] Service init failed: {exc}")
            return view.json_response(False, error='Payment service unavailable', status=503)

        result = service.process_payment_notification(data)

        if result.get('success'):
            _link_click_to_transaction(data)
            logger.info(f"[{request_id}] Payment processed: {result.get('transaction_id')}")
            return view.json_response(True, data={
                'message':        'Payment processed successfully',
                'transaction_id': result.get('transaction_id'),
                'status':         result.get('status'),
            })

        logger.error(f"[{request_id}] Payment processing failed: {result.get('error')}")
        return view.json_response(False, error=result.get('error', 'Processing failed'), status=400)

    except Exception as exc:
        logger.exception(f"[{request_id}] Unexpected error: {exc}")
        return view.json_response(False, error='Unexpected error', status=500)


def _link_click_to_transaction(notification_data: dict) -> None:
    """Tie the most recent unlinked PaymentLinkClick for the bill to the new transaction."""
    try:
        bill_reference = notification_data.get('bill_reference')
        txn_id         = notification_data.get('transaction_id')

        txn  = PaymentTransaction.objects.filter(transaction_id=txn_id).first()
        bill = BopsBills.objects.filter(bill_number=bill_reference, ).first()
        if not txn or not bill:
            return

        unlinked = PaymentLinkClick.objects.filter(
            business_bill=bill, payment__isnull=True
        ).order_by('-clicked_at').first()

        if unlinked:
            unlinked.payment = txn
            unlinked.save(update_fields=['payment'])

    except Exception as exc:
        logger.error(f"Could not link click to transaction: {exc}")


# ===========================================================================
# Authenticated / admin views
# ===========================================================================

@login_required
@require_http_methods(["GET"])
def get_payment_status(request: HttpRequest, bill_id: int,
                       bill_type: str = 'business') -> JsonResponse:
    """Get payment status for a BopsBill."""
    view = PaymentViewMixin()
    try:
        bill   = get_object_or_404(BopsBills, id=bill_id, )
        txn_qs = PaymentTransaction.objects.filter(business_bill=bill).order_by('-initiated_at')

        bill_info = {
            'bill_number':  bill.bill_number,
            'total_amount': str(bill.total_amount),
            'status':       bill.status,
            'due_date':     bill.due_date,
            'paid_date':    getattr(bill, 'paid_date', None),
        }

        latest = txn_qs.first()
        if latest:
            all_paid   = list(txn_qs.filter(status='completed').values('amount', 'completed_at', 'payment_method'))
            total_paid = sum(Decimal(str(p['amount'])) for p in all_paid) if all_paid else Decimal('0')
            balance    = Decimal(str(bill.total_amount)) - total_paid
            return view.json_response(True, data={
                'bill': bill_info,
                'latest_payment': {
                    'status':                 latest.status,
                    'amount':                 str(latest.amount),
                    'transaction_id':         latest.transaction_id,
                    'provider_transaction_id':latest.provider_transaction_id,
                    'payment_date':           latest.completed_at,
                    'payment_method':         latest.payment_method,
                    'payment_channel':        latest.payment_channel,
                    'payer_name':             latest.payer_name,
                    'initiated_at':           latest.initiated_at,
                },
                'all_payments':  all_paid,
                'total_paid':    str(total_paid),
                'balance_due':   str(balance),
                'is_fully_paid': balance <= 0,
            })

        return view.json_response(True, data={
            'bill':    bill_info,
            'status':  'not_paid',
            'message': 'No payment found for this bill',
        })

    except Exception as exc:
        logger.exception(f"Error getting payment status: {exc}")
        return view.json_response(False, error=str(exc), status=500)


@login_required
@require_http_methods(["GET"])
@never_cache
def list_payment_transactions(request: HttpRequest) -> JsonResponse:
    """List payment transactions with pagination and filtering."""
    view = PaymentViewMixin()
    try:
        page         = int(request.GET.get('page', 1))
        page_size    = min(int(request.GET.get('page_size', DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
        status_f     = request.GET.get('status')
        date_from    = request.GET.get('date_from')
        date_to      = request.GET.get('date_to')
        search_query = request.GET.get('search', '').strip()

        qs = PaymentTransaction.objects.select_related(
            'provider', 'business_bill', 'business_bill__business',
        ).order_by('-initiated_at')

        if status_f:  qs = qs.filter(status=status_f)
        if date_from: qs = qs.filter(initiated_at__date__gte=date_from)
        if date_to:   qs = qs.filter(initiated_at__date__lte=date_to)
        if search_query:
            qs = qs.filter(
                Q(transaction_id__icontains=search_query) |
                Q(provider_transaction_id__icontains=search_query) |
                Q(business_bill__bill_number__icontains=search_query) |
                Q(payer_name__icontains=search_query) |
                Q(payer_phone__icontains=search_query)
            )

        summary = qs.aggregate(
            total_count=Count('id'),
            total_amount=Sum('amount', filter=Q(status='completed')),
            pending_count=Count('id', filter=Q(status='pending')),
            completed_count=Count('id', filter=Q(status='completed')),
            failed_count=Count('id', filter=Q(status='failed')),
        )

        paginator    = Paginator(qs, page_size)
        current_page = paginator.get_page(page)

        return view.json_response(True, data={
            'transactions': [_format_transaction(t) for t in current_page.object_list],
            'pagination': {
                'current_page':  current_page.number,
                'total_pages':   paginator.num_pages,
                'total_records': paginator.count,
                'page_size':     page_size,
                'has_next':      current_page.has_next(),
                'has_previous':  current_page.has_previous(),
            },
            'summary': {
                'total_count':     summary['total_count'],
                'total_amount':    str(summary['total_amount'] or 0),
                'pending_count':   summary['pending_count'],
                'completed_count': summary['completed_count'],
                'failed_count':    summary['failed_count'],
            },
        })

    except ValueError as exc:
        return view.json_response(False, error=f'Invalid parameter: {exc}', status=400)
    except Exception as exc:
        logger.exception(f"Error listing transactions: {exc}")
        return view.json_response(False, error=str(exc), status=500)


def _format_transaction(t: 'PaymentTransaction') -> Dict[str, Any]:
    """Serialise a PaymentTransaction to a dict."""
    bill_info: Dict[str, Any] = {}
    if t.business_bill:
        biz = t.business_bill.business
        bill_info = {
            'bill_number':       t.business_bill.bill_number,
            'bill_type':         'business',
            'bill_type_display': 'Business Permit',
            'reference': {
                'business_id':    biz.id,
                'business_name':  biz.business_name,
                'account_number': biz.account_number,
            },
        }
    return {
        'id':                       t.id,
        'transaction_id':           t.transaction_id,
        'provider_transaction_id':  t.provider_transaction_id,
        'amount':                   str(t.amount),
        'status':                   t.status,
        'status_display':           t.get_status_display(),
        'payment_method':           t.payment_method,
        'payment_channel':          t.payment_channel,
        'payer': {
            'name':  t.payer_name,
            'phone': t.payer_phone,
            'email': t.payer_email,
        },
        'provider': {'id': t.provider.id, 'name': t.provider.name},
        'bill':     bill_info,
        'timestamps': {
            'initiated': t.initiated_at,
            'completed': t.completed_at,
        },
        'metadata': t.metadata,
    }


# Keep old name as alias so any existing import still works
format_transaction_data = _format_transaction


@login_required
@require_http_methods(["GET"])
def get_transaction_detail(request: HttpRequest, transaction_id: str) -> JsonResponse:
    """Get full detail for a transaction including notifications."""
    view = PaymentViewMixin()
    try:
        txn  = get_object_or_404(PaymentTransaction,
                                  Q(id=transaction_id) | Q(transaction_id=transaction_id))
        data = _format_transaction(txn)
        data['notifications'] = [
            {'id': n.id, 'processed': n.processed, 'error': n.error, 'created_at': n.created_at}
            for n in txn.notifications.all().order_by('-created_at')
        ]
        return view.json_response(True, data={'transaction': data})
    except Exception as exc:
        logger.exception(f"Error getting transaction detail: {exc}")
        return view.json_response(False, error=str(exc), status=500)


@login_required
@require_http_methods(["GET"])
def get_payment_providers(request: HttpRequest) -> JsonResponse:
    """Return all active payment providers."""
    view = PaymentViewMixin()
    try:
        providers = list(PaymentProvider.objects.filter(is_active=True).values('id', 'name', 'provider_type'))
        return view.json_response(True, data={'providers': providers})
    except Exception as exc:
        logger.exception(exc)
        return view.json_response(False, error=str(exc), status=500)


@login_required
@require_http_methods(["POST"])
def retry_failed_notification(request: HttpRequest, notification_id: int) -> JsonResponse:
    """Re-process a failed webhook notification (staff only)."""
    view = PaymentViewMixin()
    if not request.user.is_staff:
        return view.json_response(False, error='Permission denied', status=403)
    try:
        notification = get_object_or_404(PaymentNotification, id=notification_id)
        if notification.processed:
            return view.json_response(False, error='Notification already processed', status=400)
        service = view.get_payment_service()
        result  = service.process_payment_notification(notification.raw_data)
        if result.get('success'):
            return view.json_response(True, data={'message': 'Notification reprocessed successfully'})
        return view.json_response(False, error=result.get('error', 'Reprocessing failed'), status=400)
    except Exception as exc:
        logger.exception(f"Error retrying notification {notification_id}: {exc}")
        return view.json_response(False, error=str(exc), status=500)


@login_required
@require_http_methods(["POST"])
def resend_bill_sms(request: HttpRequest, bill_id: int) -> JsonResponse:
    """Manually resend the billing SMS for a BopsBill."""
    view = PaymentViewMixin()
    try:
        bill    = get_object_or_404(BopsBills, id=bill_id, )
        ok, res = send_bops_billing_sms(bill)

        if ok:
            BopsBills.objects.filter(pk=bill.pk).update(status='sent', sent_date=timezone.now())
            return view.json_response(True, data={
                'message':     f'SMS resent for bill {bill.bill_number}',
                'bill_number': bill.bill_number,
            })

        return view.json_response(False, error=f'SMS failed: {res}', status=502)
    except Exception as exc:
        logger.exception(f"Error resending SMS for bill {bill_id}: {exc}")
        return view.json_response(False, error=str(exc), status=500)