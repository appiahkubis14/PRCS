import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation

from core.models import Bops
# from from.models import Bops

logger = logging.getLogger(__name__)

# Main page view
@login_required
def bops_properties_page(request):
    """Render the Bops properties management page"""
    return render(request, 'core/main/property-registry/bops_properties.html')

# API Views
@csrf_exempt
@require_http_methods(["GET"])
def list_bops_properties(request):
    """List all Bops properties with pagination and search"""
    try:
        # Get query parameters
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 1000))
        search = request.GET.get('search', '')
        
        # Base queryset - exclude soft-deleted items
        queryset = Bops.objects.filter(is_deleted=False)
        
        # Apply search if provided
        if search:
            queryset = queryset.filter(
                Q(account_number__icontains=search) |
                Q(business_name__icontains=search) |
                Q(owner_name__icontains=search) |
                Q(location__icontains=search) |
                Q(street_name__icontains=search) |
                Q(phone_number__icontains=search) |
                Q(business_email__icontains=search) |
                Q(business_category__icontains=search) |
                Q(business_class__icontains=search) |
                Q(division__icontains=search)
            )
        
        # Order by account_number
        queryset = queryset.order_by('account_number')
        
        # Paginate
        paginator = Paginator(queryset, page_size)
        properties_page = paginator.get_page(page)
        
        # Prepare response data
        data = []
        for prop in properties_page:
            data.append({
                'id': prop.id,
                'account_number': prop.account_number,
                'business_name': prop.business_name,
                'owner_name': prop.owner_name,
                'business_category': prop.business_category,
                'business_class': prop.business_class,
                'location': prop.location,
                'street_name': prop.street_name,
                'house_number': prop.house_number,
                'digital_address': prop.digital_address,
                'address': prop.address,
                'phone_number': prop.phone_number,
                'phone_number_primary': prop.phone_number_primary,
                'business_email': prop.business_email,
                'email': prop.email,
                'division': prop.division,
                'block': prop.block,
                'flat_rate': float(prop.flat_rate) if prop.flat_rate else None,
                'structure_id': prop.structure_id,
                'centroid': prop.centroid,
                'lat': float(prop.lat) if prop.lat else None,
                'lng': float(prop.lng) if prop.lng else None,
                'source_sheet': prop.source_sheet,
                'created_at': prop.created_at.strftime('%Y-%m-%d %H:%M:%S') if prop.created_at else None,
                'updated_at': prop.updated_at.strftime('%Y-%m-%d %H:%M:%S') if prop.updated_at else None,
            })
        
        return JsonResponse({
            'data': data,
            'pagination': {
                'current_page': properties_page.number,
                'total_pages': paginator.num_pages,
                'total_records': paginator.count,
                'page_size': page_size,
                'has_next': properties_page.has_next(),
                'has_previous': properties_page.has_previous(),
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing Bops properties: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def get_bops_property(request, property_id):
    """Get a single Bops property by ID"""
    try:
        property = get_object_or_404(Bops, id=property_id, is_deleted=False)
        
        data = {
            'id': property.id,
            'account_number': property.account_number,
            'business_name': property.business_name,
            'owner_name': property.owner_name,
            'business_category': property.business_category,
            'business_class': property.business_class,
            'location': property.location,
            'street_name': property.street_name,
            'house_number': property.house_number,
            'digital_address': property.digital_address,
            'address': property.address,
            'phone_number': property.phone_number,
            'phone_number_primary': property.phone_number_primary,
            'business_email': property.business_email,
            'email': property.email,
            'division': property.division,
            'block': property.block,
            'flat_rate': float(property.flat_rate) if property.flat_rate else None,
            'structure_id': property.structure_id,
            'centroid': property.centroid,
            'lat': float(property.lat) if property.lat else None,
            'lng': float(property.lng) if property.lng else None,
            'source_sheet': property.source_sheet,
            'created_at': property.created_at.strftime('%Y-%m-%d %H:%M:%S') if property.created_at else None,
            'updated_at': property.updated_at.strftime('%Y-%m-%d %H:%M:%S') if property.updated_at else None,
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        logger.error(f"Error getting Bops property {property_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def create_bops_property(request):
    """Create a new Bops property"""
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        if not data.get('account_number'):
            return JsonResponse({'error': 'Account number is required'}, status=400)
        
        if not data.get('business_name'):
            return JsonResponse({'error': 'Business name is required'}, status=400)
        
        # Check if account number already exists
        if Bops.objects.filter(account_number=data['account_number'], is_deleted=False).exists():
            return JsonResponse({'error': f"Account number '{data['account_number']}' already exists"}, status=400)
        
        # Create new property
        property = Bops()
        
        # Set fields
        property.account_number = data.get('account_number')
        property.business_name = data.get('business_name')
        property.owner_name = data.get('owner_name', '')
        property.business_category = data.get('business_category', '')
        property.business_class = data.get('business_class', '')
        property.location = data.get('location', '')
        property.street_name = data.get('street_name', '')
        property.house_number = data.get('house_number', '')
        property.digital_address = data.get('digital_address', '')
        property.address = data.get('address', '')
        property.phone_number = data.get('phone_number', '')
        property.phone_number_primary = data.get('phone_number_primary', '')
        property.business_email = data.get('business_email', '')
        property.email = data.get('email', '')
        property.division = data.get('division', '')
        property.block = data.get('block', '')
        
        # Handle decimal fields
        if data.get('flat_rate'):
            try:
                property.flat_rate = Decimal(str(data['flat_rate']))
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid flat rate value'}, status=400)
        
        property.structure_id = data.get('structure_id', '')
        property.centroid = data.get('centroid', '')
        
        # Handle coordinates
        if data.get('lat'):
            try:
                property.lat = Decimal(str(data['lat']))
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid latitude value'}, status=400)
        
        if data.get('lng'):
            try:
                property.lng = Decimal(str(data['lng']))
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid longitude value'}, status=400)
        
        property.source_sheet = data.get('source_sheet', '')
        
        # Set added_by if user is authenticated
        if request.user.is_authenticated:
            property.added_by = request.user
        
        # Save the property (this will also handle geom calculation)
        property.full_clean()
        property.save()
        
        return JsonResponse({
            'message': 'Property created successfully',
            'id': property.id,
            'account_number': property.account_number
        }, status=201)
        
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Error creating Bops property: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["PUT"])
def update_bops_property(request, property_id):
    """Update an existing Bops property"""
    try:
        property = get_object_or_404(Bops, id=property_id, is_deleted=False)
        data = json.loads(request.body)
        
        # Check if account number is being changed and if it already exists
        new_account_number = data.get('account_number')
        if new_account_number and new_account_number != property.account_number:
            if Bops.objects.filter(account_number=new_account_number, is_deleted=False).exclude(id=property_id).exists():
                return JsonResponse({'error': f"Account number '{new_account_number}' already exists"}, status=400)
            property.account_number = new_account_number
        
        # Update fields
        if 'business_name' in data:
            property.business_name = data['business_name']
        if 'owner_name' in data:
            property.owner_name = data['owner_name']
        if 'business_category' in data:
            property.business_category = data['business_category']
        if 'business_class' in data:
            property.business_class = data['business_class']
        if 'location' in data:
            property.location = data['location']
        if 'street_name' in data:
            property.street_name = data['street_name']
        if 'house_number' in data:
            property.house_number = data['house_number']
        if 'digital_address' in data:
            property.digital_address = data['digital_address']
        if 'address' in data:
            property.address = data['address']
        if 'phone_number' in data:
            property.phone_number = data['phone_number']
        if 'phone_number_primary' in data:
            property.phone_number_primary = data['phone_number_primary']
        if 'business_email' in data:
            property.business_email = data['business_email']
        if 'email' in data:
            property.email = data['email']
        if 'division' in data:
            property.division = data['division']
        if 'block' in data:
            property.block = data['block']
        if 'flat_rate' in data:
            try:
                property.flat_rate = Decimal(str(data['flat_rate'])) if data['flat_rate'] else None
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid flat rate value'}, status=400)
        if 'structure_id' in data:
            property.structure_id = data['structure_id']
        if 'centroid' in data:
            property.centroid = data['centroid']
        if 'lat' in data:
            try:
                property.lat = Decimal(str(data['lat'])) if data['lat'] else None
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid latitude value'}, status=400)
        if 'lng' in data:
            try:
                property.lng = Decimal(str(data['lng'])) if data['lng'] else None
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid longitude value'}, status=400)
        if 'source_sheet' in data:
            property.source_sheet = data['source_sheet']
        
        # Set modified_by if user is authenticated
        if request.user.is_authenticated:
            property.modified_by = request.user
        
        # Save the property
        property.full_clean()
        property.save()
        
        return JsonResponse({
            'message': 'Property updated successfully',
            'id': property.id
        })
        
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Error updating Bops property {property_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_bops_property(request, property_id):
    """Soft delete a Bops property"""
    try:
        property = get_object_or_404(Bops, id=property_id, is_deleted=False)
        
        # Soft delete
        property.is_deleted = True
        property.deleted_at = timezone.now()
        
        if request.user.is_authenticated:
            property.deleted_by = request.user
        
        property.save()
        
        return JsonResponse({
            'message': 'Property deleted successfully',
            'id': property_id
        })
        
    except Exception as e:
        logger.error(f"Error deleting Bops property {property_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def bulk_delete_bops_properties(request):
    """Bulk soft delete multiple Bops properties"""
    try:
        data = json.loads(request.body)
        property_ids = data.get('property_ids', [])
        
        if not property_ids:
            return JsonResponse({'error': 'No property IDs provided'}, status=400)
        
        # Get all properties that exist and are not deleted
        properties = Bops.objects.filter(id__in=property_ids, is_deleted=False)
        
        if not properties.exists():
            return JsonResponse({'error': 'No valid properties found to delete'}, status=404)
        
        # Soft delete each property
        now = timezone.now()
        for prop in properties:
            prop.is_deleted = True
            prop.deleted_at = now
            if request.user.is_authenticated:
                prop.deleted_by = request.user
        
        # Bulk update
        Bops.objects.bulk_update(properties, ['is_deleted', 'deleted_at', 'deleted_by'])
        
        return JsonResponse({
            'message': f'{len(properties)} properties deleted successfully',
            'deleted_ids': list(properties.values_list('id', flat=True))
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Error bulk deleting Bops properties: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def export_bops_properties(request):
    """Export Bops properties in various formats"""
    try:
        format_type = request.GET.get('format', 'json')
        search = request.GET.get('search', '')
        
        # Get queryset
        queryset = Bops.objects.filter(is_deleted=False)
        
        # Apply search if provided
        if search:
            queryset = queryset.filter(
                Q(account_number__icontains=search) |
                Q(business_name__icontains=search) |
                Q(owner_name__icontains=search)
            )
        
        # Order by account_number
        queryset = queryset.order_by('account_number')
        
        # Prepare data
        data = []
        for prop in queryset:
            data.append({
                'account_number': prop.account_number,
                'business_name': prop.business_name,
                'owner_name': prop.owner_name,
                'business_category': prop.business_category,
                'business_class': prop.business_class,
                'location': prop.location,
                'street_name': prop.street_name,
                'house_number': prop.house_number,
                'digital_address': prop.digital_address,
                'address': prop.address,
                'phone_number': prop.phone_number,
                'phone_number_primary': prop.phone_number_primary,
                'business_email': prop.business_email,
                'email': prop.email,
                'division': prop.division,
                'block': prop.block,
                'flat_rate': float(prop.flat_rate) if prop.flat_rate else None,
                'structure_id': prop.structure_id,
                'centroid': prop.centroid,
                'lat': float(prop.lat) if prop.lat else None,
                'lng': float(prop.lng) if prop.lng else None,
                'source_sheet': prop.source_sheet,
                'created_at': prop.created_at.strftime('%Y-%m-%d %H:%M:%S') if prop.created_at else None,
            })
        
        if format_type == 'json':
            return JsonResponse({'data': data}, json_dumps_params={'indent': 2})
        else:
            # For other formats, you might want to implement CSV/Excel export
            # This is a placeholder
            return JsonResponse({'error': f'Format {format_type} not implemented yet'}, status=400)
            
    except Exception as e:
        logger.error(f"Error exporting Bops properties: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)