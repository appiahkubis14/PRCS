# api/serializers.py - Fixed version with integer IDs

from rest_framework import serializers
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


# ============================================================
# Auth Serializers
# ============================================================

class RequestOTPSerializer(serializers.Serializer):
    """Request OTP code"""
    email = serializers.EmailField()


class VerifyOTPSerializer(serializers.Serializer):
    """Verify OTP code"""
    email = serializers.EmailField()
    code = serializers.CharField(min_length=6, max_length=6)
    expoPushToken = serializers.CharField(required=False, allow_blank=True)


# api/serializers.py - Backward compatible LoginSerializer

class LoginSerializer(serializers.Serializer):
    """Login with employee ID and password - supports both 'password' and 'passwords'"""
    employee_id = serializers.CharField(max_length=50)
    password = serializers.CharField(min_length=1, write_only=True, required=False)
    passwords = serializers.CharField(min_length=1, write_only=True, required=False)
    expoPushToken = serializers.CharField(required=False, allow_blank=True, write_only=True)
    
    def validate(self, attrs):
        # Support both 'password' and 'passwords' field names
        password = attrs.get('password') or attrs.get('passwords')
        
        if not password:
            raise serializers.ValidationError({
                'password': 'Password is required'
            })
        
        # Remove the old field to avoid confusion
        attrs.pop('passwords', None)
        attrs['password'] = password
        
        return attrs

class RefreshTokenSerializer(serializers.Serializer):
    """Refresh access token"""
    refreshToken = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    """Change user password"""
    currentPassword = serializers.CharField(min_length=1)
    newPassword = serializers.CharField(min_length=6)


class UserSerializer(serializers.Serializer):
    """User response serializer matching documentation"""
    id = serializers.IntegerField()  # Changed from CharField to IntegerField
    employeeId = serializers.CharField()
    name = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField()
    role = serializers.CharField()
    supervisorId = serializers.IntegerField(allow_null=True)  # Changed to IntegerField
    isActive = serializers.BooleanField()
    createdAt = serializers.DateTimeField()
    updatedAt = serializers.DateTimeField()
    
    def to_representation(self, instance):
        # Handle Staff objects with user relationship
        if hasattr(instance, 'user') and instance.user:
            user = instance.user
            return {
                'id': user.id,  # Integer ID
                'employeeId': instance.employee_id,
                'name': user.get_full_name() or user.username,
                'email': user.email,
                'phone': instance.phone,
                'role': instance.role,
                'supervisorId': instance.supervisor.id if instance.supervisor else None,
                'isActive': instance.is_active,
                'createdAt': user.date_joined,
                'updatedAt': user.last_login or user.date_joined
            }
        # Handle User objects with staff_profile
        elif hasattr(instance, 'staff_profile'):
            staff = instance.staff_profile
            return {
                'id': instance.id,  # Integer ID
                'employeeId': staff.employee_id,
                'name': instance.get_full_name() or instance.username,
                'email': instance.email,
                'phone': staff.phone,
                'role': staff.role,
                'supervisorId': staff.supervisor.id if staff.supervisor else None,
                'isActive': staff.is_active,
                'createdAt': instance.date_joined,
                'updatedAt': instance.last_login or instance.date_joined
            }
        else:
            return {
                'id': instance.id,  # Integer ID
                'employeeId': '',
                'name': instance.get_full_name() or instance.username,
                'email': instance.email,
                'phone': '',
                'role': '',
                'supervisorId': None,
                'isActive': instance.is_active,
                'createdAt': instance.date_joined,
                'updatedAt': instance.last_login or instance.date_joined
            }


# ============================================================
# Polygon Serializers
# ============================================================

class CoordinatePointSerializer(serializers.Serializer):
    """Single coordinate point"""
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()


class PolygonSerializer(serializers.Serializer):
    """Polygon response serializer matching documentation"""
    id = serializers.CharField()  # Polygon ID is string (e.g., "GEMA-15-001-0001")
    division = serializers.IntegerField()
    block = serializers.IntegerField()
    location = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField()
    accessed = serializers.BooleanField()
    latitude = serializers.FloatField(allow_null=True)
    longitude = serializers.FloatField(allow_null=True)
    coordinates = serializers.ListField(
        child=CoordinatePointSerializer(),
        required=False,
        default=list
    )
    updatedAt = serializers.DateTimeField(source='updated_at')
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['property'] = instance.property  # Add property field separately
        return data


# ============================================================
# Location Verification Serializers
# ============================================================

class LocationSerializer(serializers.Serializer):
    """Location verification data"""
    status = serializers.ChoiceField(choices=['verified', 'proximity', 'unverified', 'mocked'])
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    accuracy = serializers.FloatField()
    timestamp = serializers.DateTimeField()
    isMocked = serializers.BooleanField(default=False)
    distanceToPolygon = serializers.FloatField(required=False, allow_null=True)


# ============================================================
# PR (Property Register) Serializers
# ============================================================

class PROwnerEntrySerializer(serializers.Serializer):
    """PR owner entry - for mode 'owners'"""
    ownerName = serializers.CharField(max_length=255)
    contact = serializers.CharField(max_length=15)
    ghanaCard = serializers.CharField(max_length=50, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    gpsAddr = serializers.CharField(max_length=100, required=False, allow_blank=True)
    streetName = serializers.CharField(max_length=255, required=False, allow_blank=True)
    title = serializers.IntegerField(min_value=0, max_value=6)
    titleOther = serializers.CharField(required=False, allow_blank=True)
    loc = serializers.IntegerField(min_value=0, max_value=12)
    locOther = serializers.CharField(required=False, allow_blank=True)
    propType = serializers.IntegerField(min_value=0, max_value=4)
    propTypeOther = serializers.CharField(required=False, allow_blank=True)
    propState = serializers.IntegerField(min_value=0, max_value=3)
    stories = serializers.IntegerField(min_value=0, max_value=5)
    rooms = serializers.IntegerField(min_value=0, max_value=11)
    occupier = serializers.IntegerField(min_value=0, max_value=3)
    occupierOther = serializers.CharField(required=False, allow_blank=True)
    msgMethod = serializers.IntegerField(min_value=0, max_value=2)
    payMethod = serializers.IntegerField(min_value=0, max_value=3)
    titleStr = serializers.CharField(required=False, allow_blank=True)
    locStr = serializers.CharField(required=False, allow_blank=True)
    typeStr = serializers.CharField(required=False, allow_blank=True)
    stateStr = serializers.CharField(required=False, allow_blank=True)
    storiesStr = serializers.CharField(required=False, allow_blank=True)
    occupierStr = serializers.CharField(required=False, allow_blank=True)
    msgMethodStr = serializers.CharField(required=False, allow_blank=True)
    payMethodStr = serializers.CharField(required=False, allow_blank=True)


class PRPOCDataSerializer(serializers.Serializer):
    """PR POC data - for mode 'poc'"""
    pocName = serializers.CharField(max_length=255)
    pocContact = serializers.CharField(max_length=15)
    pocRel = serializers.IntegerField(min_value=0, max_value=5)
    pocRelOther = serializers.CharField(required=False, allow_blank=True)
    ownerName = serializers.CharField(max_length=255)
    contact = serializers.CharField(max_length=15)
    ghanaCard = serializers.CharField(max_length=50, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    gpsAddr = serializers.CharField(max_length=100, required=False, allow_blank=True)
    streetName = serializers.CharField(max_length=255, required=False, allow_blank=True)
    title = serializers.IntegerField(min_value=0, max_value=6)
    titleOther = serializers.CharField(required=False, allow_blank=True)
    loc = serializers.IntegerField(min_value=0, max_value=12)
    locOther = serializers.CharField(required=False, allow_blank=True)
    propType = serializers.IntegerField(min_value=0, max_value=4)
    propTypeOther = serializers.CharField(required=False, allow_blank=True)
    propState = serializers.IntegerField(min_value=0, max_value=3)
    stories = serializers.IntegerField(min_value=0, max_value=5)
    rooms = serializers.IntegerField(min_value=0, max_value=11)
    msgMethod = serializers.IntegerField(min_value=0, max_value=2)
    payMethod = serializers.IntegerField(min_value=0, max_value=3)
    relStr = serializers.CharField(required=False, allow_blank=True)


class PRSkipDataSerializer(serializers.Serializer):
    """PR skip data - for mode 'skip'"""
    reason = serializers.CharField(max_length=255)
    notes = serializers.CharField(required=False, allow_blank=True)


class PRNADataSerializer(serializers.Serializer):
    """PR not applicable data - for mode 'na'"""
    reason = serializers.CharField(max_length=255)


class PRSerializer(serializers.Serializer):
    """PR data serializer - handles all modes"""
    mode = serializers.ChoiceField(choices=['owners', 'poc', 'skip', 'na'])
    
    def to_internal_value(self, data):
        mode = data.get('mode')
        result = {'mode': mode}
        
        if mode == 'owners':
            entries = data.get('entries', [])
            if not entries:
                raise serializers.ValidationError({"entries": "Entries required for owners mode"})
            entries_validator = PROwnerEntrySerializer(data=entries, many=True)
            entries_validator.is_valid(raise_exception=True)
            result['entries'] = entries_validator.validated_data
        else:
            entry_data = data.get('data', {})
            if not entry_data:
                raise serializers.ValidationError({"data": f"Data required for {mode} mode"})
            
            if mode == 'poc':
                data_validator = PRPOCDataSerializer(data=entry_data)
            elif mode == 'skip':
                data_validator = PRSkipDataSerializer(data=entry_data)
            elif mode == 'na':
                data_validator = PRNADataSerializer(data=entry_data)
            else:
                raise serializers.ValidationError(f"Unknown mode: {mode}")
            
            data_validator.is_valid(raise_exception=True)
            result['data'] = data_validator.validated_data
        
        return result


# ============================================================
# BOP (Business Operating Permit) Serializers
# ============================================================

class BOPOwnerDataSerializer(serializers.Serializer):
    """BOP owner data - for mode 'owner'"""
    structOwner = serializers.CharField(max_length=255)
    title = serializers.IntegerField(min_value=0, max_value=6)
    titleOther = serializers.CharField(required=False, allow_blank=True)
    bizOwner = serializers.CharField(max_length=255)
    tin = serializers.CharField(max_length=50, required=False, allow_blank=True)
    contact = serializers.CharField(max_length=15)
    email = serializers.EmailField(required=False, allow_blank=True)
    age = serializers.CharField(required=False, allow_blank=True)
    gender = serializers.IntegerField(min_value=0, max_value=1)
    bizName = serializers.CharField(max_length=255, required=False, allow_blank=True)
    bizType = serializers.CharField(max_length=200)
    bizSubType = serializers.CharField(max_length=200, required=False, allow_blank=True)
    category = serializers.CharField(max_length=100, required=False, allow_blank=True)
    nature = serializers.IntegerField(min_value=0, max_value=3)
    natureOther = serializers.CharField(required=False, allow_blank=True)
    structure = serializers.IntegerField(min_value=0, max_value=3)
    structureOther = serializers.CharField(required=False, allow_blank=True)
    loc = serializers.IntegerField(min_value=0, max_value=12)
    locOther = serializers.CharField(required=False, allow_blank=True)
    landmark = serializers.CharField(max_length=255, required=False, allow_blank=True)
    gpsAddr = serializers.CharField(max_length=100, required=False, allow_blank=True)
    permitNo = serializers.CharField(max_length=100, required=False, allow_blank=True)
    msgMethod = serializers.IntegerField(min_value=0, max_value=2, required=False, allow_null=True)
    payMethod = serializers.IntegerField(min_value=0, max_value=3, required=False, allow_null=True)
    titleStr = serializers.CharField(required=False, allow_blank=True)
    natureStr = serializers.CharField(required=False, allow_blank=True)
    structStr = serializers.CharField(required=False, allow_blank=True)
    locStr = serializers.CharField(required=False, allow_blank=True)
    msgMethodStr = serializers.CharField(required=False, allow_blank=True)
    payMethodStr = serializers.CharField(required=False, allow_blank=True)


class BOPPOCDataSerializer(serializers.Serializer):
    """BOP POC data - for mode 'poc'"""
    pocName = serializers.CharField(max_length=255)
    pocContact = serializers.CharField(max_length=15)
    pocRel = serializers.IntegerField(min_value=0, max_value=4)
    pocRelOther = serializers.CharField(required=False, allow_blank=True)
    structOwner = serializers.CharField(max_length=255)
    title = serializers.IntegerField(min_value=0, max_value=6)
    titleOther = serializers.CharField(required=False, allow_blank=True)
    bizOwner = serializers.CharField(max_length=255)
    tin = serializers.CharField(max_length=50, required=False, allow_blank=True)
    contact = serializers.CharField(max_length=15)
    email = serializers.EmailField(required=False, allow_blank=True)
    age = serializers.CharField(required=False, allow_blank=True)
    gender = serializers.IntegerField(min_value=0, max_value=1)
    bizName = serializers.CharField(max_length=255, required=False, allow_blank=True)
    bizType = serializers.CharField(max_length=200)
    bizSubType = serializers.CharField(max_length=200, required=False, allow_blank=True)
    category = serializers.CharField(max_length=100, required=False, allow_blank=True)
    nature = serializers.IntegerField(min_value=0, max_value=3)
    natureOther = serializers.CharField(required=False, allow_blank=True)
    structure = serializers.IntegerField(min_value=0, max_value=3)
    structureOther = serializers.CharField(required=False, allow_blank=True)
    loc = serializers.IntegerField(min_value=0, max_value=12)
    locOther = serializers.CharField(required=False, allow_blank=True)
    landmark = serializers.CharField(max_length=255, required=False, allow_blank=True)
    gpsAddr = serializers.CharField(max_length=100, required=False, allow_blank=True)
    permitNo = serializers.CharField(max_length=100, required=False, allow_blank=True)
    msgMethod = serializers.IntegerField(min_value=0, max_value=2, required=False, allow_null=True)
    payMethod = serializers.IntegerField(min_value=0, max_value=3, required=False, allow_null=True)
    relStr = serializers.CharField(required=False, allow_blank=True)


class BOPEntrySerializer(serializers.Serializer):
    """BOP entry serializer - handles both owner and poc modes"""
    mode = serializers.ChoiceField(choices=['owner', 'poc'])
    
    def to_internal_value(self, data):
        mode = data.get('mode')
        bop_data = data.get('data', {})
        
        if not bop_data:
            raise serializers.ValidationError({"data": "Data required for BOP entry"})
        
        if mode == 'owner':
            data_validator = BOPOwnerDataSerializer(data=bop_data)
        elif mode == 'poc':
            data_validator = BOPPOCDataSerializer(data=bop_data)
        else:
            raise serializers.ValidationError(f"Unknown mode: {mode}")
        
        data_validator.is_valid(raise_exception=True)
        
        return {
            'mode': mode,
            'data': data_validator.validated_data
        }


# ============================================================
# Revision Serializers
# ============================================================

class RevisionEntrySerializer(serializers.Serializer):
    """Revision entry for rejected submissions"""
    entryIndex = serializers.IntegerField()
    revisionOf = serializers.IntegerField()  # Changed from UUIDField to IntegerField


class RevisionsSerializer(serializers.Serializer):
    """Revisions container"""
    pr = RevisionEntrySerializer(many=True, required=False)
    bop = RevisionEntrySerializer(many=True, required=False)


# ============================================================
# Submission Data Serializer
# ============================================================

class SubmissionDataSerializer(serializers.Serializer):
    """Complete submission data container"""
    pr = PRSerializer(required=False, allow_null=True)
    businesses = BOPEntrySerializer(many=True, required=False)
    location = LocationSerializer(required=False, allow_null=True)
    revisions = RevisionsSerializer(required=False, allow_null=True)


class SyncItemSerializer(serializers.Serializer):
    """Single sync item"""
    id = serializers.CharField()  # Changed from UUIDField to CharField (client-generated UUID as string)
    polygonId = serializers.CharField(max_length=50)
    sessionId = serializers.CharField(required=False)  # Changed from UUIDField to CharField
    action = serializers.ChoiceField(choices=['submit', 'pass'])
    data = SubmissionDataSerializer(required=False, default=dict)
    collectorId = serializers.IntegerField()  # Changed from UUIDField to IntegerField
    submittedAt = serializers.DateTimeField()


class SyncBatchSerializer(serializers.Serializer):
    """Batch sync request"""
    items = SyncItemSerializer(many=True)


# ============================================================
# Rejected Entries Serializers
# ============================================================

class RejectedEntrySerializer(serializers.Serializer):
    """Rejected entry response"""
    id = serializers.IntegerField()  # Changed from UUIDField to IntegerField
    polygonId = serializers.CharField()
    sessionId = serializers.CharField()  # Changed from UUIDField to CharField
    entryType = serializers.ChoiceField(choices=['pr', 'bop'])
    entryIndex = serializers.IntegerField()
    mode = serializers.CharField()
    data = serializers.JSONField()
    reviewNotes = serializers.CharField(allow_blank=True)
    reviewedAt = serializers.DateTimeField(allow_null=True)


# ============================================================
# Notification Serializers
# ============================================================

class NotificationSerializer(serializers.Serializer):
    """Notification response matching documentation"""
    id = serializers.IntegerField()  # Changed from UUIDField to IntegerField
    type = serializers.ChoiceField(choices=['rejected', 'approved', 'assignment', 'reassign', 'info'])
    title = serializers.CharField()
    body = serializers.CharField()
    entityId = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()


# ============================================================
# Settings Serializers
# ============================================================

class LookupValueSerializer(serializers.Serializer):
    """Single lookup value"""
    slug = serializers.CharField()
    label = serializers.CharField()
    sortOrder = serializers.IntegerField()


class LookupGroupSerializer(serializers.Serializer):
    """Lookup group with values"""
    slug = serializers.CharField()
    label = serializers.CharField()
    allowsCustom = serializers.BooleanField()
    values = LookupValueSerializer(many=True)
    sortOrder = serializers.IntegerField()


class FormLookupsDataSerializer(serializers.Serializer):
    """Form lookups data"""
    version = serializers.CharField()
    groups = LookupGroupSerializer(many=True)


class BusinessCategorySerializer(serializers.Serializer):
    """Business category with amount"""
    slug = serializers.CharField()
    label = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    sortOrder = serializers.IntegerField()


class BusinessSubTypeSerializer(serializers.Serializer):
    """Business sub-type with categories"""
    slug = serializers.CharField()
    name = serializers.CharField()
    categories = BusinessCategorySerializer(many=True)
    sortOrder = serializers.IntegerField()


class BusinessTypeSerializer(serializers.Serializer):
    """Business type with sub-types or categories"""
    slug = serializers.CharField()
    name = serializers.CharField()
    coaCode = serializers.CharField()
    duration = serializers.CharField()
    subTypes = BusinessSubTypeSerializer(many=True, required=False, allow_null=True)
    categories = BusinessCategorySerializer(many=True, required=False, allow_null=True)
    sortOrder = serializers.IntegerField()


# ============================================================
# Health Response
# ============================================================

class HealthResponseSerializer(serializers.Serializer):
    """Health check response"""
    status = serializers.CharField()
    timestamp = serializers.DateTimeField()


# ============================================================
# Error Response Serializer
# ============================================================

class ErrorResponseSerializer(serializers.Serializer):
    """Standard error response"""
    success = serializers.BooleanField(default=False)
    error = serializers.CharField()