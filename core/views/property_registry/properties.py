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
from core.models import Polygon

logger = logging.getLogger(__name__)

# Main page view
@login_required
def properties_page(request):
    """Render the properties management page"""
    return render(request, 'core/main/property-registry/properties.html')

# API Views
# @csrf_exempt
# @require_http_methods(["GET"])
# def list_properties(request):
#     """List all properties with pagination and search"""
#     try:
#         # Get query parameters
#         page = int(request.GET.get('page', 1))
#         page_size = int(request.GET.get('page_size', 10000))
#         search = request.GET.get('search', '')
        
#         # Base queryset - exclude soft-deleted items
#         queryset = Polygon.objects.all()
        
#         # Apply search if provided
#         if search:
#             queryset = queryset.filter(
#                 Q(address__icontains=search) |
#                 Q(g_code__icontains=search) |
#                 Q(gpsname__icontains=search) |
#                 Q(region__icontains=search) |
#                 Q(district__icontains=search) |
#                 Q(street__icontains=search) |
#                 Q(addressv1__icontains=search)
#             )
        
#         # Order by id
#         queryset = queryset.order_by('-id')
        
#         # Paginate
#         paginator = Paginator(queryset, page_size)
#         properties_page = paginator.get_page(page)
        
#         # Prepare response data
#         data = []
#         for prop in properties_page:
#             data.append({
#                 'id': prop.id,
#                 'address': prop.address,
#                 'g_code': prop.g_code,
#                 'gpsname': prop.gpsname,
#                 # 'zone': {
#                 #     'id': prop.zone.id,
#                 #     'name': prop.zone.name,
#                 #     'code': prop.zone.code
#                 # } if prop.zone else None,
#                 # 'property_type': {
#                 #     'id': prop.property_type.id,
#                 #     'name': prop.property_type.name,
#                 #     'code': prop.property_type.code
#                 # } if prop.property_type else None,
#                 'area_in_me': float(prop.area_in_me) if prop.area_in_me else None,
#                 'region': prop.region,
#                 'district': prop.district,
#                 'postcode': prop.postcode,
#                 'street': prop.street,
#                 'area': str(prop.area) if prop.area else None,
#                 'latitude': float(prop.latitude) if prop.latitude else None,
#                 'longitude': float(prop.longitude) if prop.longitude else None,
#                 'nlat': float(prop.nlat) if prop.nlat else None,
#                 'slat': float(prop.slat) if prop.slat else None,
#                 'wlong': float(prop.wlong) if prop.wlong else None,
#                 'elong': float(prop.elong) if prop.elong else None,
#                 'area': str(prop.area) if prop.area else None,
#                 'addressv1': prop.addressv1,
#                 'coordinates': prop.coordinates,
#                 'geom': prop.geom.geojson if prop.geom else None,
#                 'created_at': prop.created_at.strftime('%Y-%m-%d %H:%M:%S') if prop.created_at else None,
#                 'updated_at': prop.updated_at.strftime('%Y-%m-%d %H:%M:%S') if prop.updated_at else None,
#             })
        
#         return JsonResponse({
#             'data': data,
#             'pagination': {
#                 'current_page': properties_page.number,
#                 'total_pages': paginator.num_pages,
#                 'total_records': paginator.count,
#                 'page_size': page_size,
#                 'has_next': properties_page.has_next(),
#                 'has_previous': properties_page.has_previous(),
#             }
#         })
        
#     except Exception as e:
#         print(f"Error listing properties: {str(e)}")
#         logger.error(f"Error listing properties: {str(e)}", exc_info=True)
#         return JsonResponse({'error': str(e)}, status=500)
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["GET"])
def list_properties(request):
    """List all properties with pagination and search using cached data"""
    try:
        # Get query parameters
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10000))
        search = request.GET.get('search', '')
        
        # Check if loading is in progress
        if cache.get('properties_loading'):
            partial_data = cache.get('properties_list_partial')
            if partial_data:
                return JsonResponse({
                    'data': [],
                    'status': 'loading',
                    'message': f'Loading properties: {len(partial_data)} loaded so far',
                    'pagination': {
                        'current_page': 1,
                        'total_pages': 0,
                        'total_records': 0,
                        'page_size': page_size,
                        'has_next': False,
                        'has_previous': False,
                    }
                }, status=202)
            else:
                return JsonResponse({
                    'data': [],
                    'status': 'loading',
                    'message': 'Property data is being loaded. Please refresh in a moment.',
                    'pagination': {
                        'current_page': 1,
                        'total_pages': 0,
                        'total_records': 0,
                        'page_size': page_size,
                        'has_next': False,
                        'has_previous': False,
                    }
                }, status=202)
        
        # Get cached properties list
        cached_properties = cache.get('properties_list_final')
        
        if cached_properties is None:
            return JsonResponse({
                'data': [],
                'status': 'error',
                'message': 'Property data not available. Please try again later.',
                'pagination': {
                    'current_page': 1,
                    'total_pages': 0,
                    'total_records': 0,
                    'page_size': page_size,
                    'has_next': False,
                    'has_previous': False,
                }
            }, status=503)
        
        # Apply search filter if provided
        if search:
            filtered_properties = []
            search_lower = search.lower()
            for prop in cached_properties:
                if (search_lower in str(prop.get('address', '')).lower() or
                    search_lower in str(prop.get('g_code', '')).lower() or
                    search_lower in str(prop.get('gpsname', '')).lower() or
                    search_lower in str(prop.get('region', '')).lower() or
                    search_lower in str(prop.get('district', '')).lower() or
                    search_lower in str(prop.get('street', '')).lower() or
                    search_lower in str(prop.get('addressv1', '')).lower()):
                    filtered_properties.append(prop)
        else:
            filtered_properties = cached_properties
        
        # Reverse to maintain order (newest first) like original queryset
        filtered_properties = list(reversed(filtered_properties))
        
        # Calculate pagination
        total_records = len(filtered_properties)
        total_pages = (total_records + page_size - 1) // page_size
        
        # Get current page data
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        page_data = filtered_properties[start_index:end_index]
        
        return JsonResponse({
            'data': page_data,
            'pagination': {
                'current_page': page,
                'total_pages': total_pages,
                'total_records': total_records,
                'page_size': page_size,
                'has_next': page < total_pages,
                'has_previous': page > 1,
            }
        })
        
    except Exception as e:
        print(f"Error listing properties: {str(e)}")
        logger.error(f"Error listing properties: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

        
@csrf_exempt
@require_http_methods(["GET"])
def get_property(request, property_id):
    """Get a single property by ID"""
    try:
        property = get_object_or_404(Polygon, id=property_id,)
        
        data = {
            'id': property.id,
            'address': property.address,
            'g_code': property.g_code,
            'gpsname': property.gpsname,
            # 'zone_id': property.zone.id if property.zone else None,
            # 'zone_name': property.zone.name if property.zone else None,
            # 'zone_code': property.zone.code if property.zone else None,
            # 'property_type_id': property.property_type.id if property.property_type else None,
            # 'property_type_name': property.property_type.name if property.property_type else None,
            # 'property_type_code': property.property_type.code if property.property_type else None,
            'area_in_me': float(property.area_in_me) if property.area_in_me else None,
            'region': property.region,
            'district': property.district,
            'postcode': property.postcode,
            'street': property.street,
            'latitude': float(property.latitude) if property.latitude else None,
            'longitude': float(property.longitude) if property.longitude else None,
            'nlat': float(property.nlat) if property.nlat else None,
            'slat': float(property.slat) if property.slat else None,
            'wlong': float(property.wlong) if property.wlong else None,
            'elong': float(property.elong) if property.elong else None,
            'area': str(property.area) if property.area else None,
            'addressv1': property.addressv1,
            'coordinates': property.coordinates,
            'created_at': property.created_at.strftime('%Y-%m-%d %H:%M:%S') if property.created_at else None,
            'updated_at': property.updated_at.strftime('%Y-%m-%d %H:%M:%S') if property.updated_at else None,
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        logger.error(f"Error getting property {property_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def get_zone_options(request):
    """Get all zones for dropdown"""
    try:
        # zones = Zone.objects.filter(is_deleted=False, is_active=True).values('id', 'name', 'code')
        # return JsonResponse({'data': list(zones)})
        pass
    except Exception as e:
        logger.error(f"Error getting zones: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def get_property_type_options(request):
    """Get all property types for dropdown"""
    try:
        # types = PropertyType.objects.filter(is_deleted=False, is_active=True).values('id', 'name', 'code')
        # return JsonResponse({'data': list(types)})
        pass
    except Exception as e:
        logger.error(f"Error getting property types: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def create_property(request):
    """Create a new property"""
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        if not data.get('zone_id'):
            return JsonResponse({'error': 'Zone is required'}, status=400)
        
        if not data.get('property_type_id'):
            return JsonResponse({'error': 'Polygon type is required'}, status=400)
        
        # Get zone and property type
        # try:
        #     zone = Zone.objects.get(id=data['zone_id'],)
        # except Zone.DoesNotExist:
        #     return JsonResponse({'error': 'Selected zone does not exist'}, status=400)
        
        # try:
        #     property_type = PropertyType.objects.get(id=data['property_type_id'],)
        # except PropertyType.DoesNotExist:
        #     return JsonResponse({'error': 'Selected property type does not exist'}, status=400)
        
        # Create new property
        property = Polygon()
        # property.zone = zone
        # property.property_type = property_type
        
        # Set fields
        property.address = data.get('address', '')
        property.g_code = data.get('g_code', '')
        property.gpsname = data.get('gpsname', '')
        property.region = data.get('region', '')
        property.district = data.get('district', '')
        property.postcode = data.get('postcode', '')
        property.street = data.get('street', '')
        property.addressv1 = data.get('addressv1', '')
        
        # Handle decimal fields
        if data.get('area_in_me'):
            try:
                property.area_in_me = Decimal(str(data['area_in_me']))
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid area in square meters value'}, status=400)
        
        if data.get('area'):
            try:
                property.area = Decimal(str(data['area']))
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid area value'}, status=400)
        
        # Handle coordinates
        if data.get('latitude'):
            try:
                property.latitude = Decimal(str(data['latitude']))
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid latitude value'}, status=400)
        
        if data.get('longitude'):
            try:
                property.longitude = Decimal(str(data['longitude']))
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid longitude value'}, status=400)
        
        if data.get('nlat'):
            try:
                property.nlat = Decimal(str(data['nlat']))
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid northern latitude value'}, status=400)
        
        if data.get('slat'):
            try:
                property.slat = Decimal(str(data['slat']))
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid southern latitude value'}, status=400)
        
        if data.get('wlong'):
            try:
                property.wlong = Decimal(str(data['wlong']))
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid western longitude value'}, status=400)
        
        if data.get('elong'):
            try:
                property.elong = Decimal(str(data['elong']))
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid eastern longitude value'}, status=400)
        
        # Handle JSON coordinates
        if data.get('coordinates'):
            try:
                if isinstance(data['coordinates'], str):
                    property.coordinates = json.loads(data['coordinates'])
                else:
                    property.coordinates = data['coordinates']
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid coordinates JSON'}, status=400)
        
        # Set added_by if user is authenticated
        if request.user.is_authenticated:
            property.added_by = request.user
        
        # Save the property
        property.full_clean()
        property.save()
        
        return JsonResponse({
            'message': 'Polygon created successfully',
            'id': property.id
        }, status=201)
        
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Error creating property: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["PUT"])
def update_property(request, property_id):
    """Update an existing property"""
    try:
        property = get_object_or_404(Polygon, id=property_id,)
        data = json.loads(request.body)
        
       
       
        # Update fields
        if 'address' in data:
            property.address = data['address']
        if 'g_code' in data:
            property.g_code = data['g_code']
        if 'gpsname' in data:
            property.gpsname = data['gpsname']
        if 'region' in data:
            property.region = data['region']
        if 'district' in data:
            property.district = data['district']
        if 'postcode' in data:
            property.postcode = data['postcode']
        if 'street' in data:
            property.street = data['street']
        if 'addressv1' in data:
            property.addressv1 = data['addressv1']
        
        # Update decimal fields
        if 'area_in_me' in data:
            try:
                property.area_in_me = Decimal(str(data['area_in_me'])) if data['area_in_me'] else None
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid area in square meters value'}, status=400)
        
        if 'area' in data:
            try:
                property.area = Decimal(str(data['area'])) if data['area'] else None
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid area value'}, status=400)
        
        if 'latitude' in data:
            try:
                property.latitude = Decimal(str(data['latitude'])) if data['latitude'] else None
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid latitude value'}, status=400)
        
        if 'longitude' in data:
            try:
                property.longitude = Decimal(str(data['longitude'])) if data['longitude'] else None
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid longitude value'}, status=400)
        
        if 'nlat' in data:
            try:
                property.nlat = Decimal(str(data['nlat'])) if data['nlat'] else None
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid northern latitude value'}, status=400)
        
        if 'slat' in data:
            try:
                property.slat = Decimal(str(data['slat'])) if data['slat'] else None
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid southern latitude value'}, status=400)
        
        if 'wlong' in data:
            try:
                property.wlong = Decimal(str(data['wlong'])) if data['wlong'] else None
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid western longitude value'}, status=400)
        
        if 'elong' in data:
            try:
                property.elong = Decimal(str(data['elong'])) if data['elong'] else None
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'error': 'Invalid eastern longitude value'}, status=400)
        
        # Update JSON coordinates
        if 'coordinates' in data:
            try:
                if isinstance(data['coordinates'], str):
                    property.coordinates = json.loads(data['coordinates']) if data['coordinates'] else None
                else:
                    property.coordinates = data['coordinates']
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid coordinates JSON'}, status=400)
        
        # Set modified_by if user is authenticated
        if request.user.is_authenticated:
            property.modified_by = request.user
        
        # Save the property
        property.full_clean()
        property.save()
        
        return JsonResponse({
            'message': 'Polygon updated successfully',
            'id': property.id
        })
        
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Error updating property {property_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)




@csrf_exempt
@require_http_methods(["DELETE"])
def delete_property(request, property_id):
    """Soft delete a property"""
    try:
        property = get_object_or_404(Polygon, id=property_id,)
        
        # Soft delete
        property.is_deleted = True
        property.deleted_at = timezone.now()
        
        if request.user.is_authenticated:
            property.deleted_by = request.user
        
        property.save()
        
        return JsonResponse({
            'message': 'Polygon deleted successfully',
            'id': property_id
        })
        
    except Exception as e:
        logger.error(f"Error deleting property {property_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def bulk_delete_properties(request):
    """Bulk soft delete multiple properties"""
    try:
        data = json.loads(request.body)
        property_ids = data.get('property_ids', [])
        
        if not property_ids:
            return JsonResponse({'error': 'No property IDs provided'}, status=400)
        
        # Get all properties that exist and are not deleted
        properties = Polygon.objects.filter(id__in=property_ids,)
        
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
        Polygon.objects.bulk_update(properties, ['is_deleted', 'deleted_at', 'deleted_by'])
        
        return JsonResponse({
            'message': f'{len(properties)} properties deleted successfully',
            'deleted_ids': list(properties.values_list('id', flat=True))
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Error bulk deleting properties: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def export_properties(request):
    """Export properties in various formats"""
    try:
        format_type = request.GET.get('format', 'json')
        search = request.GET.get('search', '')
        
        # Get queryset
        queryset = Polygon.objects.filter(is_deleted=False).select_related('zone', 'property_type')
        
        # Apply search if provided
        if search:
            queryset = queryset.filter(
                Q(address__icontains=search) |
                Q(g_code__icontains=search) |
                Q(gpsname__icontains=search)
            )
        
        # Order by id
        queryset = queryset.order_by('-id')
        
        # Prepare data
        data = []
        for prop in queryset:
            data.append({
                'id': prop.id,
                'address': prop.address,
                'g_code': prop.g_code,
                'gpsname': prop.gpsname,
                'zone': prop.zone.name if prop.zone else None,
                'zone_code': prop.zone.code if prop.zone else None,
                'property_type': prop.property_type.name if prop.property_type else None,
                'property_type_code': prop.property_type.code if prop.property_type else None,
                'area_in_me': float(prop.area_in_me) if prop.area_in_me else None,
                'region': prop.region,
                'district': prop.district,
                'postcode': prop.postcode,
                'street': prop.street,
                'latitude': float(prop.latitude) if prop.latitude else None,
                'longitude': float(prop.longitude) if prop.longitude else None,
                'created_at': prop.created_at.strftime('%Y-%m-%d %H:%M:%S') if prop.created_at else None,
            })
        
        if format_type == 'json':
            return JsonResponse({'data': data}, json_dumps_params={'indent': 2})
        else:
            # For other formats, you might want to implement CSV/Excel export
            # This is a placeholder
            return JsonResponse({'error': f'Format {format_type} not implemented yet'}, status=400)
            
    except Exception as e:
        logger.error(f"Error exporting properties: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)