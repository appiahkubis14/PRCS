from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from import_export.fields import Field
from import_export.widgets import ForeignKeyWidget, DateWidget, DecimalWidget
from .models import *

# Import-Export Resources
class UserRoleResource(resources.ModelResource):
    class Meta:
        model = UserRole
        import_id_fields = ['name']
        fields = ('id', 'name', 'permissions', 'description', 'created_at', 'updated_at', 
                 'is_deleted', 'added_by', 'modified_by', 'deleted_at', 'deleted_by')
        export_order = ('id', 'name', 'permissions', 'description', 'created_at', 'updated_at', 
                       'is_deleted', 'added_by', 'modified_by', 'deleted_at', 'deleted_by')

class UserProfileResource(resources.ModelResource):
    user = Field(attribute='user', column_name='user', widget=ForeignKeyWidget(User, 'username'))
    role = Field(attribute='role', column_name='role', widget=ForeignKeyWidget(UserRole, 'name'))
    added_by = Field(attribute='added_by', column_name='added_by', widget=ForeignKeyWidget(User, 'username'))
    modified_by = Field(attribute='modified_by', column_name='modified_by', widget=ForeignKeyWidget(User, 'username'))
    deleted_by = Field(attribute='deleted_by', column_name='deleted_by', widget=ForeignKeyWidget(User, 'username'))
    
    class Meta:
        model = UserProfile
        fields = ('id', 'user', 'role', 'phone', 'is_active', 'created_at', 'updated_at',
                 'is_deleted', 'added_by', 'modified_by', 'deleted_at', 'deleted_by')
        export_order = ('id', 'user', 'role', 'phone', 'is_active', 'created_at', 'updated_at',
                       'is_deleted', 'added_by', 'modified_by', 'deleted_at', 'deleted_by')

class RegionResource(resources.ModelResource):
    added_by = Field(attribute='added_by', column_name='added_by', widget=ForeignKeyWidget(User, 'username'))
    modified_by = Field(attribute='modified_by', column_name='modified_by', widget=ForeignKeyWidget(User, 'username'))
    deleted_by = Field(attribute='deleted_by', column_name='deleted_by', widget=ForeignKeyWidget(User, 'username'))
    
    class Meta:
        model = Region
        import_id_fields = ['reg_code']
        fields = ('id', 'region', 'reg_code', 'pilot', 'geom', 'created_at', 'updated_at',
                 'is_deleted', 'added_by', 'modified_by', 'deleted_at', 'deleted_by')
        export_order = ('id', 'region', 'reg_code', 'pilot', 'geom', 'created_at', 'updated_at',
                       'is_deleted', 'added_by', 'modified_by', 'deleted_at', 'deleted_by')

class DistrictResource(resources.ModelResource):
    region_foreignkey = Field(attribute='region_foreignkey', column_name='region', widget=ForeignKeyWidget(Region, 'reg_code'))
    added_by = Field(attribute='added_by', column_name='added_by', widget=ForeignKeyWidget(User, 'username'))
    modified_by = Field(attribute='modified_by', column_name='modified_by', widget=ForeignKeyWidget(User, 'username'))
    deleted_by = Field(attribute='deleted_by', column_name='deleted_by', widget=ForeignKeyWidget(User, 'username'))
    
    class Meta:
        model = District
        import_id_fields = ['district_code']
        fields = ('id', 'district', 'district_code', 'region', 'reg_code', 'region_foreignkey', 
                 'geom', 'created_at', 'updated_at', 'is_deleted', 'added_by', 'modified_by', 
                 'deleted_at', 'deleted_by')
        export_order = ('id', 'district', 'district_code', 'region', 'reg_code', 'region_foreignkey', 
                       'geom', 'created_at', 'updated_at', 'is_deleted', 'added_by', 'modified_by', 
                       'deleted_at', 'deleted_by')

class ZoneResource(resources.ModelResource):
    added_by = Field(attribute='added_by', column_name='added_by', widget=ForeignKeyWidget(User, 'username'))
    modified_by = Field(attribute='modified_by', column_name='modified_by', widget=ForeignKeyWidget(User, 'username'))
    deleted_by = Field(attribute='deleted_by', column_name='deleted_by', widget=ForeignKeyWidget(User, 'username'))
    
    class Meta:
        model = Zone
        import_id_fields = ['code']
        fields = ('id', 'name', 'code', 'zone_type', 'boundary', 'description', 'is_active', 
                 'created_at', 'updated_at', 'is_deleted', 'added_by', 'modified_by', 
                 'deleted_at', 'deleted_by')
        export_order = ('id', 'name', 'code', 'zone_type', 'boundary', 'description', 'is_active', 
                       'created_at', 'updated_at', 'is_deleted', 'added_by', 'modified_by', 
                       'deleted_at', 'deleted_by')

class PropertyTypeResource(resources.ModelResource):
    added_by = Field(attribute='added_by', column_name='added_by', widget=ForeignKeyWidget(User, 'username'))
    modified_by = Field(attribute='modified_by', column_name='modified_by', widget=ForeignKeyWidget(User, 'username'))
    deleted_by = Field(attribute='deleted_by', column_name='deleted_by', widget=ForeignKeyWidget(User, 'username'))
    
    class Meta:
        model = PropertyType
        import_id_fields = ['code']
        fields = ('id', 'name', 'code', 'description', 'base_rate', 'is_active', 'created_at', 
                 'updated_at', 'is_deleted', 'added_by', 'modified_by', 'deleted_at', 'deleted_by')
        export_order = ('id', 'name', 'code', 'description', 'base_rate', 'is_active', 'created_at', 
                       'updated_at', 'is_deleted', 'added_by', 'modified_by', 'deleted_at', 'deleted_by')

class PropertyResource(resources.ModelResource):
    zone = Field(attribute='zone', column_name='zone', widget=ForeignKeyWidget(Zone, 'code'))
    property_type = Field(attribute='property_type', column_name='property_type', widget=ForeignKeyWidget(PropertyType, 'code'))
    added_by = Field(attribute='added_by', column_name='added_by', widget=ForeignKeyWidget(User, 'username'))
    modified_by = Field(attribute='modified_by', column_name='modified_by', widget=ForeignKeyWidget(User, 'username'))
    deleted_by = Field(attribute='deleted_by', column_name='deleted_by', widget=ForeignKeyWidget(User, 'username'))
    
    class Meta:
        model = Property
        fields = ('id', 'address', 'coordinates', 'zone', 'property_type', 'geom', 'g_code', 
                 'area_in_me', 'gpsname', 'region', 'district', 'postcode', 'nlat', 'slat', 
                 'wlong', 'elong', 'area', 'addressv1', 'street', 'latitude', 'longitude',
                 'created_at', 'updated_at', 'is_deleted', 'added_by', 'modified_by', 
                 'deleted_at', 'deleted_by')
        export_order = ('id', 'address', 'coordinates', 'zone', 'property_type', 'geom', 'g_code', 
                       'area_in_me', 'gpsname', 'region', 'district', 'postcode', 'nlat', 'slat', 
                       'wlong', 'elong', 'area', 'addressv1', 'street', 'latitude', 'longitude',
                       'created_at', 'updated_at', 'is_deleted', 'added_by', 'modified_by', 
                       'deleted_at', 'deleted_by')

class PropertyOwnerResource(resources.ModelResource):
    property = Field(attribute='property', column_name='property', widget=ForeignKeyWidget(Property, 'id'))
    added_by = Field(attribute='added_by', column_name='added_by', widget=ForeignKeyWidget(User, 'username'))
    modified_by = Field(attribute='modified_by', column_name='modified_by', widget=ForeignKeyWidget(User, 'username'))
    deleted_by = Field(attribute='deleted_by', column_name='deleted_by', widget=ForeignKeyWidget(User, 'username'))
    
    class Meta:
        model = PropertyOwner
        fields = ('id', 'property', 'owner_name', 'owner_type', 'id_number', 'phone_number', 
                 'email', 'address', 'ownership_percentage', 'is_primary_owner', 'start_date', 
                 'end_date', 'created_at', 'updated_at', 'is_deleted', 'added_by', 'modified_by', 
                 'deleted_at', 'deleted_by')
        export_order = ('id', 'property', 'owner_name', 'owner_type', 'id_number', 'phone_number', 
                       'email', 'address', 'ownership_percentage', 'is_primary_owner', 'start_date', 
                       'end_date', 'created_at', 'updated_at', 'is_deleted', 'added_by', 'modified_by', 
                       'deleted_at', 'deleted_by')

class TaxRateResource(resources.ModelResource):
    zone = Field(attribute='zone', column_name='zone', widget=ForeignKeyWidget(Zone, 'code'))
    property_type = Field(attribute='property_type', column_name='property_type', widget=ForeignKeyWidget(PropertyType, 'code'))
    created_by = Field(attribute='created_by', column_name='created_by', widget=ForeignKeyWidget(User, 'username'))
    added_by = Field(attribute='added_by', column_name='added_by', widget=ForeignKeyWidget(User, 'username'))
    modified_by = Field(attribute='modified_by', column_name='modified_by', widget=ForeignKeyWidget(User, 'username'))
    deleted_by = Field(attribute='deleted_by', column_name='deleted_by', widget=ForeignKeyWidget(User, 'username'))
    
    class Meta:
        model = TaxRate
        fields = ('id', 'zone', 'property_type', 'rate', 'effective_from', 'effective_to', 
                 'description', 'created_by', 'created_at', 'updated_at', 'is_deleted', 
                 'added_by', 'modified_by', 'deleted_at', 'deleted_by')
        export_order = ('id', 'zone', 'property_type', 'rate', 'effective_from', 'effective_to', 
                       'description', 'created_by', 'created_at', 'updated_at', 'is_deleted', 
                       'added_by', 'modified_by', 'deleted_at', 'deleted_by')

class BopsResource(resources.ModelResource):
    added_by = Field(attribute='added_by', column_name='added_by', widget=ForeignKeyWidget(User, 'username'))
    modified_by = Field(attribute='modified_by', column_name='modified_by', widget=ForeignKeyWidget(User, 'username'))
    deleted_by = Field(attribute='deleted_by', column_name='deleted_by', widget=ForeignKeyWidget(User, 'username'))
    
    class Meta:
        model = Bops
        import_id_fields = ['account_number']
        fields = (
            'id', 'account_number', 'business_name', 'house_number', 'digital_address', 
            'location', 'street_name', 'phone_number', 'business_email', 'address',
            'structure_id', 'centroid', 'lng', 'lat', 'block', 'division',
            'business_category', 'business_class', 'flat_rate',
            'owner_name', 'email', 'phone_number_primary', 'source_sheet', 'geom',
            'created_at', 'updated_at', 'is_deleted', 'added_by', 'modified_by', 
            'deleted_at', 'deleted_by'
        )
        skip_unchanged = True
        report_skipped = True
        use_bulk = True
        batch_size = 100
        export_order = (
            'id', 'account_number', 'business_name', 'house_number', 'digital_address', 
            'location', 'street_name', 'phone_number', 'business_email', 'address',
            'structure_id', 'centroid', 'lng', 'lat', 'block', 'division',
            'business_category', 'business_class', 'flat_rate',
            'owner_name', 'email', 'phone_number_primary', 'source_sheet', 'geom',
            'created_at', 'updated_at', 'is_deleted', 'added_by', 'modified_by', 
            'deleted_at', 'deleted_by'
        )

class BopsBillsResource(resources.ModelResource):
    business = Field(attribute='business', column_name='business', widget=ForeignKeyWidget(Bops, 'account_number'))
    added_by = Field(attribute='added_by', column_name='added_by', widget=ForeignKeyWidget(User, 'username'))
    modified_by = Field(attribute='modified_by', column_name='modified_by', widget=ForeignKeyWidget(User, 'username'))
    deleted_by = Field(attribute='deleted_by', column_name='deleted_by', widget=ForeignKeyWidget(User, 'username'))
    
    class Meta:
        model = BopsBills
        import_id_fields = ['bill_number']
        fields = (
            'id', 'business', 'bill_number', 'billing_year', 'tax_amount',
            'penalty_amount', 'discount_amount', 'total_amount', 'status',
            'generated_date', 'due_date', 'sent_date', 'paid_date',
            'notes', 'last_clicked_at', 'click_count', 'last_click_ip',
            'created_at', 'updated_at', 'is_deleted', 'added_by', 'modified_by', 
            'deleted_at', 'deleted_by'
        )
        skip_unchanged = True
        report_skipped = True
        use_bulk = True
        batch_size = 100
        export_order = (
            'id', 'business', 'bill_number', 'billing_year', 'tax_amount',
            'penalty_amount', 'discount_amount', 'total_amount', 'status',
            'generated_date', 'due_date', 'sent_date', 'paid_date',
            'notes', 'last_clicked_at', 'click_count', 'last_click_ip',
            'created_at', 'updated_at', 'is_deleted', 'added_by', 'modified_by', 
            'deleted_at', 'deleted_by'
        )

class PaymentProviderResource(resources.ModelResource):
    class Meta:
        model = PaymentProvider
        import_id_fields = ['name']
        fields = ('id', 'name', 'provider_type', 'api_base_url', 'api_key', 'api_secret',
                 'webhook_secret', 'is_active', 'config', 'created_at', 'updated_at')
        export_order = ('id', 'name', 'provider_type', 'api_base_url', 'api_key', 'api_secret',
                       'webhook_secret', 'is_active', 'config', 'created_at', 'updated_at')

class PaymentTransactionResource(resources.ModelResource):
    provider = Field(attribute='provider', column_name='provider', widget=ForeignKeyWidget(PaymentProvider, 'name'))
    business_bill = Field(attribute='business_bill', column_name='business_bill', widget=ForeignKeyWidget(BopsBills, 'bill_number'))
    
    class Meta:
        model = PaymentTransaction
        import_id_fields = ['transaction_id']
        fields = ('id', 'transaction_id', 'bill_type', 'business_bill', 'amount', 'provider', 
                 'provider_transaction_id', 'status', 'payer_name', 'payer_phone', 'payer_email', 
                 'payment_method', 'payment_channel', 'metadata', 'error_message', 
                 'initiated_at', 'completed_at')
        export_order = ('id', 'transaction_id', 'bill_type', 'business_bill', 'amount', 'provider', 
                       'provider_transaction_id', 'status', 'payer_name', 'payer_phone', 'payer_email', 
                       'payment_method', 'payment_channel', 'metadata', 'error_message', 
                       'initiated_at', 'completed_at')

class PaymentNotificationResource(resources.ModelResource):
    transaction = Field(attribute='transaction', column_name='transaction', widget=ForeignKeyWidget(PaymentTransaction, 'transaction_id'))
    provider = Field(attribute='provider', column_name='provider', widget=ForeignKeyWidget(PaymentProvider, 'name'))
    
    class Meta:
        model = PaymentNotification
        fields = ('id', 'transaction', 'provider', 'raw_data', 'processed', 'processed_at', 
                 'error', 'created_at')
        export_order = ('id', 'transaction', 'provider', 'raw_data', 'processed', 'processed_at', 
                       'error', 'created_at')

class PaymentLinkClickResource(resources.ModelResource):
    business_bill = Field(attribute='business_bill', column_name='business_bill', widget=ForeignKeyWidget(BopsBills, 'bill_number'))
    payment = Field(attribute='payment', column_name='payment', widget=ForeignKeyWidget(PaymentTransaction, 'transaction_id'))
    
    class Meta:
        model = PaymentLinkClick
        fields = ('id', 'bill_type', 'business_bill', 'link_type', 'ip_address', 'user_agent', 
                 'referer', 'session_id', 'clicked_at', 'payment')
        export_order = ('id', 'bill_type', 'business_bill', 'link_type', 'ip_address', 'user_agent', 
                       'referer', 'session_id', 'clicked_at', 'payment')

class VersionTblResource(resources.ModelResource):
    added_by = Field(attribute='added_by', column_name='added_by', widget=ForeignKeyWidget(User, 'username'))
    modified_by = Field(attribute='modified_by', column_name='modified_by', widget=ForeignKeyWidget(User, 'username'))
    deleted_by = Field(attribute='deleted_by', column_name='deleted_by', widget=ForeignKeyWidget(User, 'username'))
    
    class Meta:
        model = versionTbl
        fields = ('id', 'version', 'created_at', 'updated_at', 'is_deleted', 'added_by', 
                 'modified_by', 'deleted_at', 'deleted_by')
        export_order = ('id', 'version', 'created_at', 'updated_at', 'is_deleted', 'added_by', 
                       'modified_by', 'deleted_at', 'deleted_by')

# Admin Classes
@admin.register(UserRole)
class UserRoleAdmin(ImportExportModelAdmin):
    resource_class = UserRoleResource
    list_display = ('name', 'description', 'created_at', 'updated_at', 'is_deleted')
    list_filter = ('name', 'is_deleted', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    fieldsets = (
        ('Role Information', {
            'fields': ('name', 'description', 'permissions')
        }),
        ('Status', {
            'fields': ('is_deleted',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'deleted_at', 'added_by', 'modified_by', 'deleted_by'),
            'classes': ('collapse',)
        }),
    )

@admin.register(UserProfile)
class UserProfileAdmin(ImportExportModelAdmin):
    resource_class = UserProfileResource
    list_display = ('user', 'role', 'phone', 'is_active', 'created_at', 'is_deleted')
    list_filter = ('role', 'is_active', 'is_deleted', 'created_at')
    search_fields = ('user__username', 'user__email', 'phone')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    autocomplete_fields = ['user', 'role']
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'role', 'phone', 'is_active')
        }),
        ('Status', {
            'fields': ('is_deleted',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'deleted_at', 'added_by', 'modified_by', 'deleted_by'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Region)
class RegionAdmin(ImportExportModelAdmin):
    resource_class = RegionResource
    list_display = ('region', 'reg_code', 'pilot', 'created_at', 'is_deleted')
    list_filter = ('pilot', 'is_deleted', 'created_at')
    search_fields = ('region', 'reg_code')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    fieldsets = (
        ('Region Information', {
            'fields': ('region', 'reg_code', 'pilot', 'geom')
        }),
        ('Status', {
            'fields': ('is_deleted',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'deleted_at', 'added_by', 'modified_by', 'deleted_by'),
            'classes': ('collapse',)
        }),
    )

@admin.register(District)
class DistrictAdmin(ImportExportModelAdmin):
    resource_class = DistrictResource
    list_display = ('district', 'district_code', 'region', 'reg_code', 'created_at', 'is_deleted')
    list_filter = ('region', 'is_deleted', 'created_at')
    search_fields = ('district', 'district_code', 'region', 'reg_code')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    autocomplete_fields = ['region_foreignkey']
    fieldsets = (
        ('District Information', {
            'fields': ('district', 'district_code', 'region', 'reg_code', 'region_foreignkey', 'geom')
        }),
        ('Status', {
            'fields': ('is_deleted',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'deleted_at', 'added_by', 'modified_by', 'deleted_by'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Zone)
class ZoneAdmin(ImportExportModelAdmin):
    resource_class = ZoneResource
    list_display = ('name', 'code', 'zone_type', 'is_active', 'created_at', 'is_deleted')
    list_filter = ('zone_type', 'is_active', 'is_deleted', 'created_at')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    fieldsets = (
        ('Zone Information', {
            'fields': ('name', 'code', 'zone_type', 'boundary', 'description', 'is_active')
        }),
        ('Status', {
            'fields': ('is_deleted',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'deleted_at', 'added_by', 'modified_by', 'deleted_by'),
            'classes': ('collapse',)
        }),
    )

@admin.register(PropertyType)
class PropertyTypeAdmin(ImportExportModelAdmin):
    resource_class = PropertyTypeResource
    list_display = ('name', 'code', 'base_rate', 'is_active', 'created_at', 'is_deleted')
    list_filter = ('is_active', 'is_deleted', 'created_at')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    fieldsets = (
        ('Property Type Information', {
            'fields': ('name', 'code', 'description', 'base_rate', 'is_active')
        }),
        ('Status', {
            'fields': ('is_deleted',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'deleted_at', 'added_by', 'modified_by', 'deleted_by'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Property)
class PropertyAdmin(ImportExportModelAdmin):
    resource_class = PropertyResource
    list_display = ('id', 'address', 'g_code', 'area_in_me', 'region', 'district', 
                   'zone', 'property_type', 'created_at', 'is_deleted')
    list_filter = ('zone', 'property_type', 'region', 'district', 'is_deleted', 'created_at')
    search_fields = ('address', 'g_code', 'gpsname', 'region', 'district', 'street')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at', 'geom')
    autocomplete_fields = ['zone', 'property_type']
    fieldsets = (
        ('Basic Information', {
            'fields': ('address', 'g_code', 'gpsname', 'coordinates')
        }),
        ('Location', {
            'fields': ('region', 'district', 'postcode', 'street', 'addressv1')
        }),
        ('Zone & Type', {
            'fields': ('zone', 'property_type')
        }),
        ('Area Measurements', {
            'fields': ('area_in_me', 'area')
        }),
        ('Geographic Coordinates', {
            'fields': ('latitude', 'longitude', 'nlat', 'slat', 'wlong', 'elong', 'geom')
        }),
        ('Status', {
            'fields': ('is_deleted',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'deleted_at', 'added_by', 'modified_by', 'deleted_by'),
            'classes': ('collapse',)
        }),
    )

@admin.register(PropertyOwner)
class PropertyOwnerAdmin(ImportExportModelAdmin):
    resource_class = PropertyOwnerResource
    list_display = ('owner_name', 'property', 'owner_type', 'is_primary_owner', 
                   'ownership_percentage', 'start_date', 'created_at', 'is_deleted')
    list_filter = ('owner_type', 'is_primary_owner', 'is_deleted', 'start_date', 'created_at')
    search_fields = ('owner_name', 'property__address', 'id_number', 'email')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    autocomplete_fields = ['property']
    fieldsets = (
        ('Owner Information', {
            'fields': ('owner_name', 'owner_type', 'id_number', 'phone_number', 'email', 'address')
        }),
        ('Property Reference', {
            'fields': ('property',)
        }),
        ('Ownership Details', {
            'fields': ('ownership_percentage', 'is_primary_owner', 'start_date', 'end_date')
        }),
        ('Status', {
            'fields': ('is_deleted',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'deleted_at', 'added_by', 'modified_by', 'deleted_by'),
            'classes': ('collapse',)
        }),
    )

@admin.register(TaxRate)
class TaxRateAdmin(ImportExportModelAdmin):
    resource_class = TaxRateResource
    list_display = ('zone', 'property_type', 'rate', 'effective_from', 'effective_to', 
                   'created_by', 'created_at', 'is_deleted')
    list_filter = ('zone', 'property_type', 'effective_from', 'is_deleted', 'created_at')
    search_fields = ('zone__name', 'property_type__name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    autocomplete_fields = ['zone', 'property_type', 'created_by']
    fieldsets = (
        ('Tax Rate Information', {
            'fields': ('zone', 'property_type', 'rate', 'description')
        }),
        ('Effective Period', {
            'fields': ('effective_from', 'effective_to')
        }),
        ('Created By', {
            'fields': ('created_by',)
        }),
        ('Status', {
            'fields': ('is_deleted',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'deleted_at', 'added_by', 'modified_by', 'deleted_by'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Bops)
class BopsAdmin(ImportExportModelAdmin):
    resource_class = BopsResource
    
    list_display = (
        'account_number', 'business_name', 'owner_name', 'business_category', 
        'business_class', 'location', 'division', 'flat_rate', 'created_at', 'is_deleted'
    )
    
    list_filter = (
        'business_category', 'business_class', 'division', 'is_deleted', 'created_at'
    )
    
    search_fields = (
        'account_number', 'business_name', 'owner_name', 'location', 
        'street_name', 'phone_number', 'business_email'
    )
    
    readonly_fields = ('created_at', 'updated_at', 'deleted_at', 'geom')
    
    list_per_page = 50
    list_max_show_all = 200
    
    fieldsets = (
        ('Business Information', {
            'fields': ('account_number', 'business_name', 'business_category', 'business_class', 'flat_rate')
        }),
        ('Location Details', {
            'fields': ('location', 'street_name', 'house_number', 'digital_address', 'address', 'block', 'division')
        }),
        ('Contact Information', {
            'fields': ('owner_name', 'phone_number', 'phone_number_primary', 'business_email', 'email')
        }),
        ('Geographic Data', {
            'fields': ('structure_id', 'centroid', 'lat', 'lng', 'geom')
        }),
        ('Source Information', {
            'fields': ('source_sheet',)
        }),
        ('Status', {
            'fields': ('is_deleted',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'deleted_at', 'added_by', 'modified_by', 'deleted_by'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('added_by', 'modified_by', 'deleted_by')
    
    def get_export_formats(self):
        from import_export.formats import base_formats
        return [
            base_formats.CSV,
            base_formats.XLSX,
            base_formats.XLS,
            base_formats.JSON,
            base_formats.TSV,
        ]
    
    def get_import_formats(self):
        from import_export.formats import base_formats
        return [
            base_formats.CSV,
            base_formats.XLSX,
            base_formats.XLS,
            base_formats.JSON,
            base_formats.TSV,
        ]

@admin.register(BopsBills)
class BopsBillsAdmin(ImportExportModelAdmin):
    resource_class = BopsBillsResource
    
    list_display = (
        'bill_number', 'business', 'billing_year', 'total_amount', 
        'status', 'due_date', 'generated_date','is_deleted'
    )
    
    list_filter = (
        'status', 'billing_year', 'is_deleted', 'generated_date', 'due_date'
    )
    
    search_fields = (
        'bill_number', 'business__business_name', 'business__account_number',
        'business__owner_name', 'notes'
    )
    
    readonly_fields = ('bill_number', 'created_at', 'updated_at', 'deleted_at', 
                      'generated_date', 'last_clicked_at', 'click_count', 'last_click_ip')
    
    list_per_page = 50
    list_max_show_all = 200
    
    date_hierarchy = 'generated_date'
    
    fieldsets = (
        ('Bill Information', {
            'fields': ('business', 'bill_number', 'billing_year', 'status')
        }),
        ('Amounts', {
            'fields': ('tax_amount', 'penalty_amount', 'discount_amount', 'total_amount')
        }),
        ('Dates', {
            'fields': ('due_date', 'sent_date', 'paid_date', 'generated_date')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('Click Tracking', {
            'fields': ('last_clicked_at', 'click_count', 'last_click_ip'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_deleted',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'deleted_at', 'added_by', 'modified_by', 'deleted_by'),
            'classes': ('collapse',)
        }),
    )
    
    autocomplete_fields = ['business']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('business', 'added_by', 'modified_by', 'deleted_by')
    
    def get_export_formats(self):
        from import_export.formats import base_formats
        return [
            base_formats.CSV,
            base_formats.XLSX,
            base_formats.XLS,
            base_formats.JSON,
            base_formats.TSV,
        ]
    
    def get_import_formats(self):
        from import_export.formats import base_formats
        return [
            base_formats.CSV,
            base_formats.XLSX,
            base_formats.XLS,
            base_formats.JSON,
            base_formats.TSV,
        ]

@admin.register(PaymentProvider)
class PaymentProviderAdmin(ImportExportModelAdmin):
    resource_class = PaymentProviderResource
    list_display = ['name', 'provider_type', 'is_active', 'created_at']
    list_filter = ['provider_type', 'is_active']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'provider_type', 'is_active')
        }),
        ('API Configuration', {
            'fields': ('api_base_url', 'api_key', 'api_secret', 'webhook_secret')
        }),
        ('Additional Configuration', {
            'fields': ('config',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(ImportExportModelAdmin):
    resource_class = PaymentTransactionResource
    list_display = ['transaction_id', 'bill_type', 'business_bill', 'amount', 'status', 
                   'initiated_at', 'completed_at']
    list_filter = ['bill_type', 'status', 'payment_method']
    search_fields = ['transaction_id', 'provider_transaction_id', 'payer_name', 'payer_phone']
    readonly_fields = ['initiated_at', 'completed_at']
    autocomplete_fields = ['business_bill', 'provider']
    fieldsets = (
        ('Transaction Information', {
            'fields': ('transaction_id', 'provider_transaction_id', 'status', 'amount')
        }),
        ('Bill Information', {
            'fields': ('bill_type', 'business_bill')
        }),
        ('Payer Information', {
            'fields': ('payer_name', 'payer_phone', 'payer_email')
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'payment_channel', 'provider')
        }),
        ('Metadata', {
            'fields': ('metadata', 'error_message'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('initiated_at', 'completed_at')
        }),
    )

@admin.register(PaymentNotification)
class PaymentNotificationAdmin(ImportExportModelAdmin):
    resource_class = PaymentNotificationResource
    list_display = ['id', 'transaction', 'provider', 'processed', 'created_at']
    list_filter = ['processed', 'provider']
    readonly_fields = ['created_at', 'processed_at']
    autocomplete_fields = ['transaction', 'provider']
    fieldsets = (
        ('Notification Information', {
            'fields': ('transaction', 'provider', 'raw_data')
        }),
        ('Processing', {
            'fields': ('processed', 'processed_at', 'error')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )

@admin.register(PaymentLinkClick)
class PaymentLinkClickAdmin(ImportExportModelAdmin):
    resource_class = PaymentLinkClickResource
    list_display = ['id', 'bill_type', 'business_bill', 'link_type', 'ip_address', 'clicked_at']
    list_filter = ['bill_type', 'link_type', 'clicked_at']
    search_fields = ['business_bill__bill_number', 'session_id', 'ip_address']
    readonly_fields = ['clicked_at']
    autocomplete_fields = ['business_bill', 'payment']
    fieldsets = (
        ('Click Information', {
            'fields': ('bill_type', 'business_bill', 'link_type')
        }),
        ('Technical Details', {
            'fields': ('ip_address', 'user_agent', 'referer', 'session_id')
        }),
        ('Tracking', {
            'fields': ('clicked_at', 'payment')
        }),
    )

@admin.register(versionTbl)
class VersionTblAdmin(ImportExportModelAdmin):
    resource_class = VersionTblResource
    list_display = ('version', 'created_at', 'updated_at', 'is_deleted')
    list_filter = ('is_deleted', 'created_at')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    fieldsets = (
        ('Version Information', {
            'fields': ('version',)
        }),
        ('Status', {
            'fields': ('is_deleted',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'deleted_at', 'added_by', 'modified_by', 'deleted_by'),
            'classes': ('collapse',)
        }),
    )