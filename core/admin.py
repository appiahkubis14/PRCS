# core/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.gis.admin import GISModelAdmin
from django.contrib.gis import forms
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from import_export.fields import Field
from import_export.widgets import ForeignKeyWidget, DateWidget, DecimalWidget, JSONWidget
from .models import *
from django.contrib.auth.models import User
from django.utils.html import format_html


# ============================================================
# Custom Widgets
# ============================================================

class GeometryWidget(JSONWidget):
    """Widget for geometry fields in export"""
    def render(self, value, obj=None):
        if value:
            return value.wkt if hasattr(value, 'wkt') else str(value)
        return ''


# ============================================================
# User Resource
# ============================================================

class UserResource(resources.ModelResource):
    supervisor = Field(attribute='supervisor', column_name='supervisor', 
                      widget=ForeignKeyWidget(UserModel, 'email'))
    
    class Meta:
        model = UserModel
        import_id_fields = ['email']
        fields = ('id', 'employee_id', 'name', 'email', 'phone', 'role', 
                 'supervisor', 'is_active', 'created_at', 'updated_at', 'expo_push_token')
        export_order = ('employee_id', 'name', 'email', 'phone', 'role', 
                       'supervisor', 'is_active', 'created_at', 'updated_at')
        skip_unchanged = True
        report_skipped = True


# ============================================================
# UserModel Admin
# ============================================================

@admin.register(UserModel)
class UserModelAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_class = UserResource
    
    list_display = ('id','employee_id', 'name', 'email', 'phone', 'role', 'get_supervisor_email','password_new', 'is_active', 'created_at')
    list_filter = ('role', 'is_active', 'created_at')
    search_fields = ('employee_id', 'name', 'email', 'phone')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['supervisor']
    
    def get_supervisor_email(self, obj):
        return obj.supervisor.email if obj.supervisor else '-'
    get_supervisor_email.short_description = 'Supervisor'
    get_supervisor_email.admin_order_field = 'supervisor__email'
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('employee_id', 'name', 'email', 'phone')
        }),
        ('Authentication', {
            'fields': ('password_hash','password_new')
        }),
        ('Role & Permissions', {
            'fields': ('role', 'supervisor', 'is_active')
        }),
        ('Mobile App', {
            'fields': ('expo_push_token',),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# ============================================================
# Polygon Resource
# ============================================================

class PolygonResource(resources.ModelResource):
    assigned_to_user = Field(attribute='assigned_to_user', column_name='assigned_to_user', 
                            widget=ForeignKeyWidget(UserModel, 'email'))
    geom = Field(attribute='geom', column_name='geom', widget=GeometryWidget())
    
    class Meta:
        model = Polygon
        import_id_fields = ['property']
        fields = ('property', 'division', 'block', 'g_code', 'area_in_me', 'district', 'postcode',
                 'nlat', 'slat', 'wlong', 'elong', 'gpsname', 'region', 'area', 'addressv1',
                 'street', 'latitude', 'longitude', 'address', 'coordinates', 'location',
                 'status', 'accessed', 'assigned_to_user', 'geom', 'created_at', 'updated_at')
        export_order = ('property', 'division', 'block', 'g_code', 'location', 'latitude', 
                       'longitude', 'status', 'accessed', 'geom', 'created_at', 'updated_at')


# ============================================================
# Polygon Admin
# ============================================================

@admin.register(Polygon)
class PolygonAdmin(GISModelAdmin, ImportExportModelAdmin):
    resource_class = PolygonResource
    
    list_display = ('property', 'division', 'block', 'g_code', 'location', 'display_geom_preview', 'status', 'accessed', 'created_at')
    list_filter = ('division', 'status', 'accessed', 'created_at')
    search_fields = ('property', 'g_code', 'location', 'address')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['assigned_to_user']
    
    def display_geom_preview(self, obj):
        if obj.geom:
            return format_html('<span style="color: green;">✓ Has Geometry</span>')
        return format_html('<span style="color: red;">✗ No Geometry</span>')
    display_geom_preview.short_description = 'Geometry'
    
    fieldsets = (
        ('Property Information', {
            'fields': ('property', 'division', 'block', 'g_code', 'location')
        }),
        ('Address Information', {
            'fields': ('district', 'region', 'area', 'addressv1', 'street', 'address', 'postcode')
        }),
        ('GPS Coordinates', {
            'fields': ('gpsname', 'nlat', 'slat', 'wlong', 'elong')
        }),
        ('Centroid Coordinates', {
            'fields': ('latitude', 'longitude')
        }),
        ('Geometry', {
            'fields': ('geom', 'coordinates'),
            'classes': ('map',)
        }),
        ('Status', {
            'fields': ('status', 'accessed', 'assigned_to_user')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# ============================================================
# Business Resource
# ============================================================

class BusinessResource(resources.ModelResource):
    business_type = Field(attribute='business_type', column_name='business_type', 
                         widget=ForeignKeyWidget(BusinessType, 'slug'))
    business_sub_type = Field(attribute='business_sub_type', column_name='business_sub_type', 
                             widget=ForeignKeyWidget(BusinessSubType, 'slug'))
    business_category_value = Field(attribute='business_category_value', column_name='business_category', 
                                   widget=ForeignKeyWidget(BusinessCategory, 'slug'))
    geometry = Field(attribute='geometry', column_name='geometry', widget=GeometryWidget())
    
    class Meta:
        model = Business
        import_id_fields = ['account_number']
        fields = ('id', 'account_number', 'business_name', 'business_category', 'business_class',
                 'owner_name', 'email', 'business_email', 'phone_number', 'phone_number_primary',
                 'house_number', 'digital_address', 'location', 'street_name', 'address',
                 'structure_id', 'centroid', 'block', 'division', 'lng', 'lat', 'geometry',
                 'flat_rate', 'business_type', 'business_sub_type', 'business_category_value',
                 'source_sheet', 'imported_from_bops', 'bops_import_date', 'is_deleted',
                 'deleted_at', 'created_at', 'updated_at')
        
        export_order = ('account_number', 'business_name', 'owner_name', 'email', 'phone_number',
                       'location', 'division', 'block', 'business_category', 'business_class',
                       'flat_rate', 'geometry', 'is_deleted', 'created_at')


# ============================================================
# Business Admin
# ============================================================
from django.contrib.gis import admin
from django.utils.safestring import mark_safe
from import_export.admin import ImportExportModelAdmin
from .models import Business
# from .resources import BusinessResource

@admin.register(Business)
class BusinessAdmin(admin.GISModelAdmin, ImportExportModelAdmin):
    resource_class = BusinessResource
    list_display = ('account_number', 'business_name', 'owner_name', 'division', 'block', 
                   'display_geometry_preview', 'flat_rate', 'is_deleted', 'created_at')
    list_filter = ('division', 'is_deleted', 'imported_from_bops', 'created_at')
    search_fields = ('account_number', 'business_name', 'owner_name', 'email', 'phone_number')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['business_type', 'business_sub_type', 'business_category_value']
    
    def display_geometry_preview(self, obj):
        if obj.geometry:
            return mark_safe('<span style="color: green;">✓ Has Geometry</span>')
        return mark_safe('<span style="color: red;">✗ No Geometry</span>')
    display_geometry_preview.short_description = 'Geometry'
    
    fieldsets = (
        ('Business Information', {
            'fields': ('account_number', 'business_name', 'business_category', 'business_class', 'flat_rate')
        }),
        ('Owner Information', {
            'fields': ('owner_name', 'email', 'business_email', 'phone_number', 'phone_number_primary')
        }),
        ('Location', {
            'fields': ('location', 'street_name', 'house_number', 'digital_address', 'address', 'block', 'division')
        }),
        ('Geographic Data', {
            'fields': ('structure_id', 'centroid', 'lat', 'lng', 'geometry'),
            'classes': ('map',)
        }),
        ('Classification', {
            'fields': ('business_type', 'business_sub_type', 'business_category_value')
        }),
        ('Metadata', {
            'fields': ('source_sheet', 'imported_from_bops', 'bops_import_date', 'is_deleted', 'deleted_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
# ============================================================
# Assignment Admin
# ============================================================

class AssignmentResource(resources.ModelResource):
    collector = Field(attribute='collector', column_name='collector', 
                     widget=ForeignKeyWidget(UserModel, 'email'))
    polygon = Field(attribute='polygon', column_name='polygon', 
                   widget=ForeignKeyWidget(Polygon, 'property'))
    assigned_by = Field(attribute='assigned_by', column_name='assigned_by', 
                       widget=ForeignKeyWidget(UserModel, 'email'))
    
    class Meta:
        model = Assignment
        fields = ('id', 'collector', 'polygon', 'assigned_by', 'assigned_at', 'status')
        export_order = ('collector', 'polygon', 'assigned_by', 'assigned_at', 'status')


@admin.register(Assignment)
class AssignmentAdmin(ImportExportModelAdmin):
    resource_class = AssignmentResource
    list_display = ('id', 'collector', 'polygon', 'assigned_by', 'assigned_at', 'status')
    list_filter = ('status', 'assigned_at')
    search_fields = ('collector__name', 'collector__email', 'polygon__property', 'polygon__g_code')
    readonly_fields = ('assigned_at',)
    autocomplete_fields = ['collector', 'polygon', 'assigned_by']


# ============================================================
# Session Admin
# ============================================================

class PREntryInline(admin.TabularInline):
    model = PREntry
    extra = 0
    fields = ('entry_index', 'mode', 'data_preview', 'status', 'review_notes', 'created_at')
    readonly_fields = ('created_at', 'data_preview')
    can_delete = False
    show_change_link = True
    
    def data_preview(self, obj):
        if obj.data:
            return format_html('<pre>{}</pre>', str(obj.data)[:100])
        return '-'
    data_preview.short_description = 'Data Preview'


class BOPEntryInline(admin.TabularInline):
    model = BOPEntry
    extra = 0
    fields = ('entry_index', 'mode', 'data_preview', 'status', 'review_notes', 'created_at')
    readonly_fields = ('created_at', 'data_preview')
    can_delete = False
    show_change_link = True
    
    def data_preview(self, obj):
        if obj.data:
            return format_html('<pre>{}</pre>', str(obj.data)[:100])
        return '-'
    data_preview.short_description = 'Data Preview'


class SessionResource(resources.ModelResource):
    polygon = Field(attribute='polygon', column_name='polygon', 
                   widget=ForeignKeyWidget(Polygon, 'property'))
    collector = Field(attribute='collector', column_name='collector', 
                     widget=ForeignKeyWidget(UserModel, 'email'))
    reviewed_by = Field(attribute='reviewed_by', column_name='reviewed_by', 
                       widget=ForeignKeyWidget(UserModel, 'email'))
    
    class Meta:
        model = Session
        fields = ('id', 'polygon', 'collector', 'status', 'reviewed_by', 'reviewed_at', 
                 'review_notes', 'submitted_at', 'location_status', 'location_lat', 
                 'location_lng', 'location_accuracy', 'location_mocked', 'location_distance',
                 'location_timestamp', 'created_at', 'updated_at')
        export_order = ('polygon', 'collector', 'status', 'submitted_at', 'reviewed_by', 
                       'reviewed_at', 'review_notes')


@admin.register(Session)
class SessionAdmin(ImportExportModelAdmin):
    resource_class = SessionResource
    list_display = ('id', 'polygon', 'collector', 'status', 'submitted_at', 'reviewed_by', 'created_at')
    list_filter = ('status', 'submitted_at', 'created_at')
    search_fields = ('polygon__property', 'polygon__g_code', 'collector__name', 'collector__email')
    readonly_fields = ('submitted_at', 'created_at', 'updated_at')
    autocomplete_fields = ['polygon', 'collector', 'reviewed_by']
    inlines = [PREntryInline, BOPEntryInline]
    
    fieldsets = (
        ('Session Information', {
            'fields': ('polygon', 'collector', 'status')
        }),
        ('Review Information', {
            'fields': ('reviewed_by', 'reviewed_at', 'review_notes')
        }),
        ('Location Data', {
            'fields': ('location_status', 'location_lat', 'location_lng', 
                      'location_accuracy', 'location_mocked', 'location_distance', 
                      'location_timestamp'),
            'classes': ('collapse',)
        }),
        ('Data', {
            'fields': ('pr_data', 'businesses'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('submitted_at', 'created_at', 'updated_at', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )


# ============================================================
# PREntry Admin
# ============================================================

class PREntryResource(resources.ModelResource):
    session = Field(attribute='session', column_name='session', 
                   widget=ForeignKeyWidget(Session, 'id'))
    reviewed_by = Field(attribute='reviewed_by', column_name='reviewed_by', 
                       widget=ForeignKeyWidget(UserModel, 'email'))
    
    class Meta:
        model = PREntry
        fields = ('id', 'session', 'entry_index', 'mode', 'data', 'status', 'reviewed_by', 
                 'reviewed_at', 'review_notes', 'revision_of', 'created_at', 'updated_at')
        export_order = ('session', 'entry_index', 'mode', 'status', 'reviewed_by', 
                       'reviewed_at', 'review_notes')


@admin.register(PREntry)
class PREntryAdmin(ImportExportModelAdmin):
    resource_class = PREntryResource
    list_display = ('id', 'session', 'entry_index', 'mode', 'status', 'created_at')
    list_filter = ('mode', 'status', 'created_at')
    search_fields = ('session__polygon__property', 'session__collector__name')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['session', 'reviewed_by']


# ============================================================
# BOPEntry Admin
# ============================================================

class BOPEntryResource(resources.ModelResource):
    session = Field(attribute='session', column_name='session', 
                   widget=ForeignKeyWidget(Session, 'id'))
    reviewed_by = Field(attribute='reviewed_by', column_name='reviewed_by', 
                       widget=ForeignKeyWidget(UserModel, 'email'))
    
    class Meta:
        model = BOPEntry
        fields = ('id', 'session', 'entry_index', 'mode', 'data', 'status', 'reviewed_by', 
                 'reviewed_at', 'review_notes', 'revision_of', 'created_at', 'updated_at')
        export_order = ('session', 'entry_index', 'mode', 'status', 'reviewed_by', 
                       'reviewed_at', 'review_notes')


@admin.register(BOPEntry)
class BOPEntryAdmin(ImportExportModelAdmin):
    resource_class = BOPEntryResource
    list_display = ('id', 'session', 'entry_index', 'mode', 'status', 'created_at')
    list_filter = ('mode', 'status', 'created_at')
    search_fields = ('session__polygon__property', 'session__collector__name')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['session', 'reviewed_by']


# ============================================================
# Bill Admin
# ============================================================

class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ('amount', 'method', 'reference', 'status', 'paid_at')
    readonly_fields = ('paid_at',)
    can_delete = False
    show_change_link = True


class BillResource(resources.ModelResource):
    session = Field(attribute='session', column_name='session', 
                   widget=ForeignKeyWidget(Session, 'id'))
    polygon = Field(attribute='polygon', column_name='polygon', 
                   widget=ForeignKeyWidget(Polygon, 'property'))
    business = Field(attribute='business', column_name='business', 
                    widget=ForeignKeyWidget(Business, 'account_number'))
    issued_by = Field(attribute='issued_by', column_name='issued_by', 
                     widget=ForeignKeyWidget(UserModel, 'email'))
    
    class Meta:
        model = Bill
        import_id_fields = ['bill_number']
        fields = ('id', 'bill_number', 'session', 'polygon', 'business', 'bill_type', 'owner_name', 
                 'owner_contact', 'owner_email', 'amount', 'arrears', 'total_due', 'amount_paid',
                 'due_date', 'status', 'tax_amount', 'penalty_amount', 'discount_amount', 'total_amount',
                 'billing_year', 'issued_by', 'issued_at', 'click_count', 'last_clicked_at', 
                 'last_click_ip', 'notes', 'deleted_at')
        export_order = ('bill_number', 'session', 'polygon', 'business', 'bill_type', 'owner_name', 
                       'owner_contact', 'owner_email', 'amount', 'arrears', 'total_due', 'amount_paid',
                       'due_date', 'status', 'issued_at')


@admin.register(Bill)
class BillAdmin(ImportExportModelAdmin):
    resource_class = BillResource
    list_display = ('bill_number', 'bill_type', 'owner_name', 'total_due', 'status', 'due_date', 'issued_at')
    list_filter = ('bill_type', 'status', 'due_date', 'issued_at', 'billing_year')
    search_fields = ('bill_number', 'owner_name', 'owner_email', 'owner_contact')
    readonly_fields = ('issued_at',)
    autocomplete_fields = ['session', 'polygon', 'business', 'issued_by']
    inlines = [PaymentInline]
    
    fieldsets = (
        ('Bill Information', {
            'fields': ('bill_number', 'bill_type', 'status', 'billing_year')
        }),
        ('Property/Business Information', {
            'fields': ('session', 'polygon', 'business')
        }),
        ('Owner Information', {
            'fields': ('owner_name', 'owner_contact', 'owner_email')
        }),
        ('Amounts', {
            'fields': ('amount', 'arrears', 'total_due', 'amount_paid', 'tax_amount', 
                      'penalty_amount', 'discount_amount', 'total_amount')
        }),
        ('Dates', {
            'fields': ('due_date', 'issued_at')
        }),
        ('Tracking', {
            'fields': ('click_count', 'last_clicked_at', 'last_click_ip', 'notes'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('deleted_at',),
            'classes': ('collapse',)
        }),
    )


# ============================================================
# Payment Admin
# ============================================================

class PaymentResource(resources.ModelResource):
    bill = Field(attribute='bill', column_name='bill', 
                widget=ForeignKeyWidget(Bill, 'bill_number'))
    reconciled_by = Field(attribute='reconciled_by', column_name='reconciled_by', 
                         widget=ForeignKeyWidget(UserModel, 'email'))
    recorded_by = Field(attribute='recorded_by', column_name='recorded_by', 
                       widget=ForeignKeyWidget(UserModel, 'email'))
    
    class Meta:
        model = Payment
        fields = ('id', 'bill', 'amount', 'method', 'reference', 'hubtel_data', 'receipt_number', 
                 'status', 'reconciled', 'reconciled_at', 'paid_at', 'created_at')
        export_order = ('bill', 'amount', 'method', 'reference', 'receipt_number', 
                       'status', 'paid_at')


@admin.register(Payment)
class PaymentAdmin(ImportExportModelAdmin):
    resource_class = PaymentResource
    list_display = ('id', 'bill', 'amount', 'method', 'status', 'reconciled', 'paid_at')
    list_filter = ('method', 'status', 'reconciled', 'paid_at')
    search_fields = ('bill__bill_number', 'reference', 'receipt_number')
    readonly_fields = ('paid_at', 'created_at')
    autocomplete_fields = ['bill', 'reconciled_by', 'recorded_by']


# ============================================================
# Business Classification Admin
# ============================================================

class BusinessSubTypeInline(admin.TabularInline):
    model = BusinessSubType
    extra = 1
    fields = ('slug', 'name', 'sort_order', 'is_active')
    ordering = ['sort_order']


class BusinessCategoryInline(admin.TabularInline):
    model = BusinessCategory
    extra = 1
    fields = ('slug', 'label', 'amount', 'sort_order', 'is_active', 'effective_from', 'effective_to')
    ordering = ['sort_order']


@admin.register(BusinessType)
class BusinessTypeAdmin(ImportExportModelAdmin):
    list_display = ('slug', 'name', 'coa_code', 'duration', 'is_active', 'sort_order', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('slug', 'name', 'coa_code')
    inlines = [BusinessSubTypeInline, BusinessCategoryInline]
    readonly_fields = ('updated_at',)


@admin.register(BusinessSubType)
class BusinessSubTypeAdmin(ImportExportModelAdmin):
    list_display = ('business_type', 'slug', 'name', 'sort_order', 'is_active', 'updated_at')
    list_filter = ('business_type', 'is_active')
    search_fields = ('slug', 'name')
    autocomplete_fields = ['business_type']
    readonly_fields = ('updated_at',)


@admin.register(BusinessCategory)
class BusinessCategoryAdmin(ImportExportModelAdmin):
    list_display = ('business_type', 'sub_type', 'slug', 'label', 'amount', 'is_active', 'effective_from', 'updated_at')
    list_filter = ('business_type', 'is_active')
    search_fields = ('slug', 'label')
    autocomplete_fields = ['business_type', 'sub_type']
    readonly_fields = ('updated_at',)


# ============================================================
# Proxy Model Admin (Backward Compatibility)
# ============================================================

@admin.register(Staff)
class StaffAdmin(ImportExportModelAdmin):
    """Alias for UserModel for backward compatibility"""
    resource_class = UserResource
    list_display = ('id','employee_id', 'name', 'email', 'phone', 'role', 'is_active')
    list_filter = ('role', 'is_active')
    search_fields = ('employee_id', 'name', 'email')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        return UserModel.objects.all()


@admin.register(Bops)
class BopsAdmin(BusinessAdmin):
    """Alias for Business model for backward compatibility"""
    pass


@admin.register(BopsBills)
class BopsBillsAdmin(BillAdmin):
    """Alias for Bill with BOP type for backward compatibility"""
    
    def get_queryset(self, request):
        return Bill.objects.filter(bill_type='bop')


@admin.register(PropertyBill)
class PropertyBillAdmin(BillAdmin):
    """Alias for Bill with PR type"""
    
    def get_queryset(self, request):
        return Bill.objects.filter(bill_type='pr')


@admin.register(BusinessBill)
class BusinessBillAdmin(BillAdmin):
    """Alias for Bill with BOP type"""
    
    def get_queryset(self, request):
        return Bill.objects.filter(bill_type='bop')


# ============================================================
# Other Model Admin Registrations
# ============================================================

@admin.register(PropertyRate)
class PropertyRateAdmin(ImportExportModelAdmin):
    list_display = ('valuation_no', 'surname', 'first_name', 'prop_type', 'division', 'block', 'imported_at')
    list_filter = ('prop_type', 'division', 'block')
    search_fields = ('valuation_no', 'surname', 'first_name', 'mobile_number', 'email', 'tin_number')
    readonly_fields = ('imported_at',)
    autocomplete_fields = ['polygon']
    
    fieldsets = (
        ('Property Information', {
            'fields': ('valuation_no', 'polygon', 'title', 'surname', 'first_name', 'prop_type', 'prop_name')
        }),
        ('Owner Information', {
            'fields': ('prop_owner', 'mobile_number', 'email', 'tin_number')
        }),
        ('Location', {
            'fields': ('house_no', 'suburb', 'division', 'block', 'street_name', 'area_zone', 'prop_address', 'landmark')
        }),
        ('Rate Information', {
            'fields': ('rate_code', 'rate_input', 'rateable_value', 'total_amount', 'current_amount')
        }),
        ('Audit Information', {
            'fields': ('imported_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(BlockBoundary)
class BlockBoundaryAdmin(GISModelAdmin):
    list_display = ('id', 'division', 'block', 'property_count', 'complete_count', 'assessed_count', 'display_geom_preview')
    list_filter = ('division',)
    search_fields = ('id',)
    
    def display_geom_preview(self, obj):
        if obj.geom:
            return format_html('<span style="color: green;">✓ Has Geometry</span>')
        return format_html('<span style="color: red;">✗ No Geometry</span>')
    display_geom_preview.short_description = 'Geometry'


@admin.register(SystemSetting)
class SystemSettingAdmin(ImportExportModelAdmin):
    list_display = ('key', 'value_truncated', 'updated_at', 'updated_by')
    search_fields = ('key',)
    readonly_fields = ('updated_at',)
    autocomplete_fields = ['updated_by']
    
    def value_truncated(self, obj):
        return obj.value[:100] if obj.value else '-'
    value_truncated.short_description = 'Value'


@admin.register(AuditLog)
class AuditLogAdmin(ImportExportModelAdmin):
    list_display = ('id', 'action', 'entity_type', 'entity_id', 'actor', 'ip_address', 'created_at')
    list_filter = ('action', 'entity_type', 'created_at')
    search_fields = ('actor__name', 'actor__email', 'entity_id', 'ip_address')
    readonly_fields = ('created_at',)
    autocomplete_fields = ['actor']


@admin.register(PaymentProvider)
class PaymentProviderAdmin(ImportExportModelAdmin):
    list_display = ('name', 'provider_type', 'is_active', 'created_at')
    list_filter = ('provider_type', 'is_active')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    
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
    list_display = ('transaction_id', 'bill', 'amount', 'status', 'payment_method', 'initiated_at')
    list_filter = ('status', 'payment_method', 'initiated_at')
    search_fields = ('transaction_id', 'provider_transaction_id', 'payer_name', 'payer_phone')
    readonly_fields = ('initiated_at',)
    autocomplete_fields = ['bill', 'provider']


@admin.register(PaymentNotification)
class PaymentNotificationAdmin(ImportExportModelAdmin):
    list_display = ('id', 'transaction', 'provider', 'processed', 'created_at')
    list_filter = ('processed', 'provider')
    readonly_fields = ('created_at', 'processed_at')
    autocomplete_fields = ['transaction', 'provider']


@admin.register(PaymentLinkClick)
class PaymentLinkClickAdmin(ImportExportModelAdmin):
    list_display = ('id', 'bill', 'bill_type', 'link_type', 'ip_address', 'clicked_at')
    list_filter = ('bill_type', 'link_type', 'clicked_at')
    search_fields = ('bill__bill_number', 'session_id', 'ip_address')
    readonly_fields = ('clicked_at',)
    autocomplete_fields = ['bill', 'payment']


@admin.register(Notification)
class NotificationAdmin(ImportExportModelAdmin):
    list_display = ('id', 'bill', 'type', 'channel', 'recipient', 'status', 'sent_at')
    list_filter = ('type', 'channel', 'status', 'sent_at')
    search_fields = ('recipient',)
    readonly_fields = ('created_at',)
    autocomplete_fields = ['bill']


@admin.register(CollectorNotification)
class CollectorNotificationAdmin(ImportExportModelAdmin):
    list_display = ('id', 'type', 'title', 'read', 'created_at')
    list_filter = ('type', 'read', 'created_at')
    search_fields = ('recipient__name', 'recipient__email', 'title')
    readonly_fields = ('created_at',)
    autocomplete_fields = ['recipient']


@admin.register(OTPCode)
class OTPCodeAdmin(ImportExportModelAdmin):
    list_display = ('email', 'attempts', 'expires_at', 'used', 'created_at')
    list_filter = ('used', 'expires_at', 'created_at')
    search_fields = ('email',)
    readonly_fields = ('code_hash', 'created_at')


@admin.register(LookupGroup)
class LookupGroupAdmin(ImportExportModelAdmin):
    list_display = ('slug', 'label', 'allows_custom', 'sort_order', 'updated_at')
    search_fields = ('slug', 'label')
    inlines = []  # LookupValue inline will be added separately


class LookupValueInline(admin.TabularInline):
    model = LookupValue
    extra = 1
    fields = ('slug', 'label', 'sort_order', 'is_active')
    ordering = ['sort_order']


# Add inline to LookupGroup after definition
LookupGroupAdmin.inlines = [LookupValueInline]


@admin.register(LookupValue)
class LookupValueAdmin(ImportExportModelAdmin):
    list_display = ('group', 'slug', 'label', 'sort_order', 'is_active', 'updated_at')
    list_filter = ('group', 'is_active')
    search_fields = ('slug', 'label')
    autocomplete_fields = ['group']


@admin.register(VersionTbl)
class VersionTblAdmin(ImportExportModelAdmin):
    list_display = ('version', 'created_at', 'updated_at', 'is_deleted')
    list_filter = ('is_deleted', 'created_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(RefreshToken)
class RefreshTokenAdmin(ImportExportModelAdmin):
    list_display = ('user', 'expires_at', 'created_at')
    list_filter = ('expires_at', 'created_at')
    search_fields = ('user__name', 'user__email')
    autocomplete_fields = ['user']


@admin.register(BankStatement)
class BankStatementAdmin(ImportExportModelAdmin):
    list_display = ('id', 'bank_name', 'statement_date', 'reference', 'amount', 'status', 'uploaded_at')
    list_filter = ('bank_name', 'status', 'statement_date')
    search_fields = ('reference', 'description')
    readonly_fields = ('uploaded_at',)
    autocomplete_fields = ['matched_payment', 'uploaded_by']


@admin.register(FeeSchedule)
class FeeScheduleAdmin(ImportExportModelAdmin):
    list_display = ('bill_type', 'category', 'sub_category', 'amount', 'effective_from', 'effective_to')
    list_filter = ('bill_type', 'effective_from')
    search_fields = ('category', 'sub_category')
    autocomplete_fields = ['created_by']


# ============================================================
# Register all models that might have been missed
# ============================================================

# Ensure all models are registered
try:
    from core.models import Business, BusinessCategory, BusinessSubType, BusinessType
    # Already registered above
except ImportError:
    pass