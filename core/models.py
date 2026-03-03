import random
import secrets
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

from django.contrib.gis.geos import Point

from django.db import models
from django.contrib.gis.db import models as gis_models
from django.contrib.auth.models import User, Group
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.postgres.fields import ArrayField
from datetime import date
import uuid
from django.contrib.gis.db.models import GeometryField
from django.contrib.auth import get_user_model


User = get_user_model()




# Custom managers for soft delete functionality
class TimeStampManager(models.Manager):
    def __init__(self, *args, **kwargs):
        self.alive_only = kwargs.pop('alive_only', True)
        super(TimeStampManager, self).__init__(*args, **kwargs)

    def get_queryset(self):
        if self.alive_only:
            return TimeStampQuerySet(self.model).filter(is_deleted=False)
        return TimeStampQuerySet(self.model)

    def hard_delete(self):
        return self.get_queryset().hard_delete()

class TimeStampQuerySet(models.QuerySet):
    def delete(self):
        return self.update(is_deleted=True)
    
    def hard_delete(self):
        return super(TimeStampQuerySet, self).delete()
    
    def alive(self):
        return self.filter(is_deleted=False)
    
    def dead(self):
        return self.filter(is_deleted=True)

class TimeStampModel(models.Model):
    """
    Abstract base model with timestamp and soft delete functionality
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='%(class)s_created')
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='%(class)s_modified')
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='%(class)s_deleted')
    
    objects = TimeStampManager()
    all_objects = models.Manager()
    
    class Meta:
        abstract = True
    
    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save()
    
    def hard_delete(self, *args, **kwargs):
        super(TimeStampModel, self).delete(*args, **kwargs)



class versionTbl(TimeStampModel):
 version = models.IntegerField(blank=True, null=True)


# Missing: User roles, departments, permissions
class UserRole(TimeStampModel):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('ceo', 'CEO'),
        ('director', 'Director'),
        ('finance_team', 'Finance Team'),
        ('assessment_team', 'Assessment Team'),
        
    )
    name = models.CharField(max_length=50, choices=ROLE_CHOICES)
    permissions = models.JSONField()  # Store specific permissions
    description = models.TextField(blank=True)

class UserProfile(TimeStampModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.ForeignKey(UserRole, on_delete=models.PROTECT)
    phone = models.CharField(max_length=15, blank=True)
    is_active = models.BooleanField(default=True)

# Region and District Models
class Region(TimeStampModel):
    region = models.CharField(max_length=250, unique=True)
    reg_code = models.CharField(max_length=10, unique=True, blank=True, null=True)
    pilot = models.BooleanField(default=False) 
    geom = GeometryField(blank=True, null=True, srid=4326)
    
    def __str__(self):
        return self.region
    
    class Meta:
        verbose_name = "Region"
        verbose_name_plural = "Regions"

class District(TimeStampModel):
    district = models.CharField(max_length=250)
    district_code = models.CharField(max_length=10, unique=True, blank=True, null=True)
    region = models.CharField(max_length=250, null=True, blank=True)
    reg_code = models.CharField(max_length=10, unique=True, blank=True, null=True)
    region_foreignkey = models.ForeignKey(
        'Region',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='districts',
        to_field='reg_code'  # This is the key change
    )
    geom = GeometryField(blank=True, null=True, srid=4326)
    
    def __str__(self):
        return f"{self.district} ({self.region})"
    
    def save(self, *args, **kwargs):
        # Auto-populate the region_foreignkey based on the reg_code
        if self.reg_code and not self.region_foreignkey:
            try:
                region_obj = Region.objects.get(reg_code=self.reg_code)
                self.region_foreignkey = region_obj
            except Region.DoesNotExist:
                pass
        super().save(*args, **kwargs)


class Department(TimeStampModel):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    code = models.CharField(max_length=10, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return self.name

class Zone(TimeStampModel):
    ZONE_TYPE_CHOICES = (
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('industrial', 'Industrial'),
        ('agricultural', 'Agricultural'),
        ('mixed_use', 'Mixed Use'),
    )
    
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    zone_type = models.CharField(max_length=20, choices=ZONE_TYPE_CHOICES)
    boundary = models.JSONField()  # GeoJSON for zone boundaries
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.zone_type})"


class PropertyType(TimeStampModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)
    base_rate = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    

class Property(TimeStampModel):
    PROPERTY_STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('under_construction', 'Under Construction'),
        ('demolished', 'Demolished'),
    )
    
    # property_id = models.CharField(max_length=20, unique=True)
    address = models.TextField(null=True, blank=True)
    coordinates = models.JSONField(null=True, blank=True)  # Latitude and longitude
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name='properties')
    property_type = models.ForeignKey(PropertyType, on_delete=models.PROTECT, related_name='properties')
    geom = GeometryField(blank=True, null=True, srid=4326)
    g_code = models.CharField(max_length=50, blank=True)  # Geographic code
    area_in_me = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Area in Square Meters")  # Alternative area field
    gpsname = models.CharField(max_length=200, blank=True, verbose_name="GPS Name")  # GPS location name
    region = models.CharField(max_length=100, blank=True)  # Region name
    district = models.CharField(max_length=100, blank=True)  # District name
    postcode = models.CharField(max_length=20, blank=True, verbose_name="Postal Code")  # Postal code
    nlat = models.DecimalField(max_digits=15, decimal_places=12, null=True, blank=True, verbose_name="Northern Latitude")  # Northern boundary latitude
    slat = models.DecimalField(max_digits=15, decimal_places=12, null=True, blank=True, verbose_name="Southern Latitude")  # Southern boundary latitude
    wlong = models.DecimalField(max_digits=15, decimal_places=12, null=True, blank=True, verbose_name="Western Longitude")  # Western boundary longitude
    elong = models.DecimalField(max_digits=15, decimal_places=12, null=True, blank=True, verbose_name="Eastern Longitude")  # Eastern boundary longitude
    area = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Area")  # Alternative area measurement
    addressv1 = models.TextField(blank=True, verbose_name="Address Version 1")  # Alternative address format
    street = models.CharField(max_length=200, blank=True)  # Street name
    latitude = models.DecimalField(max_digits=15, decimal_places=12, null=True, blank=True)  # Point latitude
    longitude = models.DecimalField(max_digits=15, decimal_places=12, null=True, blank=True)  # Point longitude


    class Meta:
        indexes = [
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['district']),
            models.Index(fields=['zone']),
        ]
  

    def __str__(self):
        return f"{self.address}"


class PropertyOwner(TimeStampModel):
    OWNER_TYPE_CHOICES = (
        ('individual', 'Individual'),
        ('company', 'Company'),
        ('government', 'Government'),
        ('trust', 'Trust'),
    )
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='owners')
    owner_name = models.CharField(max_length=200)
    owner_type = models.CharField(max_length=20, choices=OWNER_TYPE_CHOICES)
    id_number = models.CharField(max_length=50, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    ownership_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    is_primary_owner = models.BooleanField(default=False)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"{self.owner_name} "

class TaxRate(TimeStampModel):
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='tax_rates')
    property_type = models.ForeignKey(PropertyType, on_delete=models.CASCADE, related_name='tax_rates')
    rate = models.DecimalField(max_digits=6, decimal_places=4)  # Tax rate as percentage
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='tax_rates_created')
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"{self.zone.name} - {self.property_type.name}: {self.rate}%"

class BillingCycle(TimeStampModel):
    CYCLE_TYPE_CHOICES = (
        ('annual', 'Annual'),
        ('semi_annual', 'Semi-Annual'),
        ('quarterly', 'Quarterly'),
        ('monthly', 'Monthly'),
    )
    
    name = models.CharField(max_length=100)
    cycle_type = models.CharField(max_length=20, choices=CYCLE_TYPE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    due_date = models.DateField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.start_date} to {self.end_date})"

class Bill(TimeStampModel):
    BILL_STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('generated', 'Generated'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    )
    
    bill_number = models.CharField(max_length=100, unique=True)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='bills')
    billing_cycle = models.ForeignKey(BillingCycle, on_delete=models.PROTECT, related_name='bills', null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2)
    penalty_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=100, choices=BILL_STATUS_CHOICES, default='draft')
    generated_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField()
    sent_date = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='bills_created')
    created_at = models.DateTimeField(auto_now_add=True)

     # Add these new fields for tracking
    last_clicked_at = models.DateTimeField(null=True, blank=True, verbose_name='Last Link Clicked')
    click_count = models.IntegerField(default=0, verbose_name='Number of Link Clicks')
    last_click_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='Last Click IP')

    def __str__(self):
        return f"Bill {self.bill_number} - {self.property.property_id}"
    
     
    def record_click(self, link_type, request):
        """Record a payment link click"""
        self.last_clicked_at = timezone.now()
        self.click_count = (self.click_count or 0) + 1
        
        # Create click record
        click = PaymentLinkClick.objects.create(
            bill_type='property',
            property_bill=self,
            link_type=link_type,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            referer=request.META.get('HTTP_REFERER', '')[:500],
            session_id=request.session.session_key or ''
        )
        
        self.last_click_ip = click.ip_address
        self.save()
        return click
    
    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class Payment(TimeStampModel):
    PAYMENT_METHOD_CHOICES = (
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('cheque', 'Cheque'),
        ('online', 'Online Payment'),
    )
    
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    
    payment_reference = models.CharField(max_length=50, unique=True)
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_date = models.DateTimeField()
    transaction_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    received_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='payments_received')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"Payment {self.payment_reference} - {self.amount}"

class Penalty(TimeStampModel):
    PENALTY_TYPE_CHOICES = (
        ('late_payment', 'Late Payment'),
        ('under_assessment', 'Under Assessment'),
        ('non_compliance', 'Non-Compliance'),
    )
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='penalties')
    penalty_type = models.CharField(max_length=20, choices=PENALTY_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    applied_date = models.DateField()
    due_date = models.DateField()
    is_paid = models.BooleanField(default=False)
    applied_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='penalties_applied')
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"Penalty - {self.property.property_id} - {self.penalty_type}"

class ServiceRequest(TimeStampModel):
    REQUEST_TYPE_CHOICES = (
        ('valuation_review', 'Valuation Review'),
        ('ownership_transfer', 'Ownership Transfer'),
        ('payment_issue', 'Payment Issue'),
        ('information_request', 'Information Request'),
        ('complaint', 'Complaint'),
    )
    
    REQUEST_STATUS_CHOICES = (
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    )
    
    request_number = models.CharField(max_length=20, unique=True)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='service_requests')
    request_type = models.CharField(max_length=30, choices=REQUEST_TYPE_CHOICES)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=REQUEST_STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=10, choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], default='medium')
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='requests_made')
    assigned_to = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='requests_assigned')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'service_requests'

    def __str__(self):
        return f"SR-{self.request_number} - {self.request_type}"

class AuditTrail(TimeStampModel):
    ACTION_CHOICES = (
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('view', 'View'),
        ('login', 'Login'),
        ('logout', 'Logout'),
    )
    
    user = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='audit_trails')
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=50)
    record_id = models.CharField(max_length=50)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_trails'
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['model_name', 'record_id']),
        ]

    def __str__(self):
        return f"{self.user.username if self.user else 'System'} - {self.action} - {self.model_name}"

class Notification(TimeStampModel):
    NOTIFICATION_TYPE_CHOICES = (
        ('bill_generated', 'Bill Generated'),
        ('payment_received', 'Payment Received'),
        ('payment_overdue', 'Payment Overdue'),
        ('service_request', 'Service Request'),
        ('system_alert', 'System Alert'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.username}"

class Report(TimeStampModel):
    REPORT_TYPE_CHOICES = (
        ('revenue_summary', 'Revenue Summary'),
        ('collection_performance', 'Collection Performance'),
        ('property_inventory', 'Property Inventory'),
        ('delinquency_report', 'Delinquency Report'),
        ('zone_analysis', 'Zone Analysis'),
        ('custom', 'Custom Report'),
    )
    
    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=30, choices=REPORT_TYPE_CHOICES)
    parameters = models.JSONField()  # Store report filters and parameters
    generated_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='reports_generated')
    file_path = models.FileField(upload_to='reports/', null=True, blank=True)
    is_automated = models.BooleanField(default=False)
    schedule = models.CharField(max_length=50, blank=True)  # For automated reports
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'reports'

    def __str__(self):
        return self.name

class GISData(TimeStampModel):
    LAYER_TYPE_CHOICES = (
        ('property_boundaries', 'Property Boundaries'),
        ('zones', 'Zones'),
        ('revenue_heatmap', 'Revenue Heatmap'),
        ('collection_density', 'Collection Density'),
        ('infrastructure', 'Infrastructure'),
    )
    
    name = models.CharField(max_length=200)
    layer_type = models.CharField(max_length=30, choices=LAYER_TYPE_CHOICES)
    geo_data = models.JSONField()  # GeoJSON data
    style_config = models.JSONField()  # Styling configuration for the layer
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='gis_data_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gis_data'

    def __str__(self):
        return f"{self.name} ({self.layer_type})"

class SystemConfiguration(TimeStampModel):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    data_type = models.CharField(max_length=20, choices=[
        ('string', 'String'),
        ('integer', 'Integer'),
        ('decimal', 'Decimal'),
        ('boolean', 'Boolean'),
        ('json', 'JSON'),
    ])
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)
    updated_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='system_configurations_updated')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'system_configurations'

    def __str__(self):
        return self.key



# Missing: Revenue tracking, expenses, budget
class Revenue(TimeStampModel):
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    revenue_type = models.CharField(max_length=50)  # tax, penalty, etc.
    period = models.DateField()  # Monthly revenue period

class Expense(TimeStampModel):
    expense_type = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField()
    expense_date = models.DateField()
    approved_by = models.ForeignKey(User, on_delete=models.PROTECT)

class Budget(TimeStampModel):
    fiscal_year = models.CharField(max_length=10)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    allocated_amount = models.DecimalField(max_digits=15, decimal_places=2)
    utilized_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)




# Missing: Customer accounts, communications
class CustomerAccount(TimeStampModel):
    property_owner = models.ForeignKey(PropertyOwner, on_delete=models.CASCADE)
    account_number = models.CharField(max_length=20, unique=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=[('active', 'Active'), ('inactive', 'Inactive')])

class Communication(TimeStampModel):
    MESSAGE_TYPE_CHOICES = (
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('notification', 'Notification'),
        ('letter', 'Letter'),
    )
    customer = models.ForeignKey(PropertyOwner, on_delete=models.CASCADE)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES)
    subject = models.CharField(max_length=200)
    content = models.TextField()
    sent_date = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(User, on_delete=models.PROTECT)



# Missing: Legal case management
class LegalCase(TimeStampModel):
    CASE_STATUS_CHOICES = (
        ('open', 'Open'),
        ('in_court', 'In Court'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    )
    case_number = models.CharField(max_length=20, unique=True)
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    case_type = models.CharField(max_length=100)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=CASE_STATUS_CHOICES)
    filed_date = models.DateField()
    resolved_date = models.DateField(null=True, blank=True)
    legal_team = models.ForeignKey(User, on_delete=models.PROTECT, related_name='legal_cases')


# Missing: Delinquency tracking
class Delinquency(TimeStampModel):
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    overdue_amount = models.DecimalField(max_digits=12, decimal_places=2)
    overdue_days = models.IntegerField()
    status = models.CharField(max_length=20, choices=[('active', 'Active'), ('resolved', 'Resolved')])
    escalation_level = models.IntegerField(default=1)  # 1, 2, 3 for different actions
    last_action_date = models.DateField()
    next_action_date = models.DateField()


# Missing: Mobile payment providers
class MobilePaymentProvider(TimeStampModel):
    name = models.CharField(max_length=100)  # MTN, Vodafone, AirtelTigo, etc.
    code = models.CharField(max_length=10, unique=True)
    is_active = models.BooleanField(default=True)
    config = models.JSONField()  # API keys, endpoints, etc.

class MobilePayment(TimeStampModel):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE)
    provider = models.ForeignKey(MobilePaymentProvider, on_delete=models.PROTECT)
    mobile_number = models.CharField(max_length=15)
    transaction_reference = models.CharField(max_length=100)
    provider_reference = models.CharField(max_length=100, blank=True)


class Bops(TimeStampModel):
    # Primary/Identification Fields
    account_number = models.CharField(max_length=100, db_column='Account_Number', verbose_name='Account Number')
    business_name = models.CharField(max_length=255, db_column='Business_Name', verbose_name='Business Name')
    house_number = models.CharField(max_length=100, blank=True, null=True, db_column='House_Number', verbose_name='House Number')
    digital_address = models.CharField(max_length=100, blank=True, null=True, db_column='Digital_Address', verbose_name='Digital Address')
    location = models.CharField(max_length=255, blank=True, null=True, db_column='Location')
    street_name = models.CharField(max_length=255, blank=True, null=True, db_column='Street_Name', verbose_name='Street Name')
    phone_number = models.CharField(max_length=50, blank=True, null=True, db_column='Phone_Number', verbose_name='Phone Number')
    business_email = models.EmailField(max_length=255, blank=True, null=True, db_column='Business_Email', verbose_name='Business Email')
    address = models.TextField(blank=True, null=True, db_column='Address')
    
    # Geographic/Structural Fields
    structure_id = models.CharField(max_length=50, blank=True, null=True, db_column='Structure_ID', verbose_name='Structure ID')
    centroid = models.CharField(max_length=100, blank=True, null=True, db_column='Centroid')
    block = models.CharField(max_length=50, blank=True, null=True, db_column='Block')
    division = models.CharField(max_length=50, blank=True, null=True, db_column='Division')
    lng = models.DecimalField(max_digits=15, decimal_places=12, blank=True, null=True, db_column='Longitude')
    lat = models.DecimalField(max_digits=15, decimal_places=12, blank=True, null=True, db_column='Latitude')
    geom = GeometryField(blank=True, null=True, srid=4326)
    
    # Business Classification Fields
    business_category = models.TextField(blank=True, null=True, db_column='Business_Category', verbose_name='Business Category')
    business_class = models.TextField(blank=True, null=True, db_column='Business_Class', verbose_name='Business Class')
    flat_rate = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, db_column='Flat_Rate', verbose_name='Flat Rate')
    
    # Owner/Contact Fields
    owner_name = models.CharField(max_length=255, blank=True, null=True, db_column='Owner_Name', verbose_name='Owner Name')
    email = models.EmailField(max_length=255, blank=True, null=True, db_column='Email')
    phone_number_primary = models.CharField(max_length=50, blank=True, null=True, db_column='Phone_Number_Primary', verbose_name='Phone Number Primary')
    source_sheet = models.CharField(max_length=100, blank=True, null=True, db_column='Source_Sheet', verbose_name='Source Sheet')
    
    class Meta:
        db_table = 'lanma_businesses'
        verbose_name = 'LANMA Business'
        verbose_name_plural = 'LANMA Businesses'
        ordering = ['account_number']
        indexes = [
            models.Index(fields=['account_number']),
            models.Index(fields=['business_name']),
            models.Index(fields=['business_category']),
            models.Index(fields=['division']),
        ]
    
    def save(self, *args, **kwargs):
        # Only calculate geom if centroid is available and geom is not set
        if not self.geom :
            try:
                # Parse centroid if it's in format "lat,lon" or similar
                if  self.lng:
                    lon = self.lng
                    lat = self.lat
                    self.geom = Point(lon, lat, srid=4326)
            except (ValueError, AttributeError):
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account_number} - {self.business_name}"


class BopsBills (TimeStampModel):
    """
    Model for Business Bills (BOPs Bills)
    Ensures that each business can only have one bill generated per year
    """
    BILL_STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('generated', 'Generated'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    )
    
    business = models.ForeignKey(
        Bops, 
        on_delete=models.CASCADE, 
        related_name='bills',
        verbose_name='Business'
    )
    bill_number = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name='Bill Number',
        blank=True,  # Allow blank so it can be auto-generated
        help_text='Auto-generated if not provided. Format: LANMA-YYYY-0001'
    )
    billing_year = models.IntegerField(verbose_name='Billing Year')
    tax_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name='Tax Amount'
    )
    penalty_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name='Penalty Amount'
    )
    discount_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name='Discount Amount'
    )
    total_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        verbose_name='Total Amount'
    )
    status = models.CharField(
        max_length=100, 
        choices=BILL_STATUS_CHOICES, 
        default='draft',
        verbose_name='Status'
    )
    generated_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Generated Date'
    )
    due_date = models.DateField(verbose_name='Due Date')
    sent_date = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name='Sent Date'
    )
    paid_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Paid Date'
    )
    # created_by = models.ForeignKey(
    #     User, 
    #     on_delete=models.PROTECT, 
    #     related_name='bops_bills_created',
    #     verbose_name='Created By'
    # )

    notes = models.TextField(blank=True, null=True, verbose_name='Notes')

     # Add these new fields for tracking
    last_clicked_at = models.DateTimeField(null=True, blank=True, verbose_name='Last Link Clicked')
    click_count = models.IntegerField(default=0, verbose_name='Number of Link Clicks')
    last_click_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='Last Click IP')
    
    # Note: created_at, updated_at, added_by, modified_by, deleted_by, deleted_at
    # are inherited from TimeStampModel
    
    class Meta:
        db_table = 'lanma_business_bills'
        verbose_name = 'Business Bill'
        verbose_name_plural = 'Business Bills'
        ordering = ['-billing_year', '-generated_date']
        # Unique constraint to ensure only one bill per business per year
        unique_together = [['business', 'billing_year']]
        indexes = [
            models.Index(fields=['business', 'billing_year']),
            models.Index(fields=['bill_number']),
            models.Index(fields=['billing_year']),
            models.Index(fields=['status']),
            models.Index(fields=['due_date']),
        ]
    
    def clean(self):
        """
        Validate that the business doesn't already have a bill for this year
        """
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        
        # If this is a new bill (not updating), check for existing bill
        if not self.pk:
            # Check if a bill already exists for this business and year
            existing_bill = BopsBills.objects.filter(
                business=self.business,
                billing_year=self.billing_year,
                is_deleted=False
            ).exclude(status='cancelled')
            
            if existing_bill.exists():
                raise ValidationError(
                    f'A bill for {self.business.business_name} already exists for the year {self.billing_year}. '
                    f'Each business can only have one bill per year.'
                )
        
        # Validate billing year is not in the future
        current_year = timezone.now().year
        if self.billing_year > current_year + 1:  # Allow one year ahead for planning
            raise ValidationError(
                f'Billing year cannot be more than one year in the future. '
                f'Current year: {current_year}, Provided: {self.billing_year}'
            )
        
        # Validate total amount
        calculated_total = self.tax_amount - self.discount_amount + self.penalty_amount
        if abs(self.total_amount - calculated_total) > 0.01:  # Allow small rounding differences
            raise ValidationError(
                f'Total amount ({self.total_amount}) does not match calculated amount '
                f'({calculated_total}). Total = Tax - Discount + Penalty'
            )
    
    def generate_bill_number(self):
        """
        Generate bill number in format: LANMA-YYYY-0001
        Returns the next sequential bill number for the billing year
        Uses database-level locking to prevent race conditions
        """
        from django.db import transaction
        from django.db.models import Max, Q
        
        if not self.billing_year:
            raise ValueError("Billing year must be set before generating bill number")
        
        # Generate prefix: LANMA-YYYY-
        prefix = f"LANMA-{self.billing_year}-"
        
        # Use database transaction with select_for_update to prevent race conditions
        with transaction.atomic():
            # Get all bill numbers for this year that match the pattern
            # Use select_for_update to lock rows and prevent concurrent access
            existing_bills = BopsBills.objects.filter(
                bill_number__startswith=prefix,
                is_deleted=False
            ).exclude(
                Q(pk=self.pk) if self.pk else Q()
            ).select_for_update()
            
            # Extract the numeric part and find the maximum
            max_number = 0
            for bill in existing_bills:
                try:
                    # Extract number from format LANMA-YYYY-NNNN
                    parts = bill.bill_number.split('-')
                    if len(parts) == 3 and parts[2].isdigit():
                        num = int(parts[2])
                        max_number = max(max_number, num)
                except (ValueError, IndexError, AttributeError):
                    continue
            
            # Increment for the new bill
            next_number = max_number + 1
            
            # Format with leading zeros (4 digits)
            bill_number = f"{prefix}{next_number:04d}"
            
            # Double-check uniqueness (in case of edge cases)
            if BopsBills.objects.filter(bill_number=bill_number, is_deleted=False).exists():
                # If somehow the number exists, try next
                next_number += 1
                bill_number = f"{prefix}{next_number:04d}"
            
            return bill_number
    
    def save(self, *args, **kwargs):
        """
        Override save to run validation, auto-generate bill number, and auto-calculate total
        """
        # Auto-generate bill number if not provided or empty
        if not self.bill_number or self.bill_number.strip() == '':
            self.bill_number = self.generate_bill_number()
        
        # Auto-calculate total if not set or if components changed
        if not self.total_amount or kwargs.get('force_recalculate', False):
            self.total_amount = self.tax_amount - self.discount_amount + self.penalty_amount
        
        # Run full validation
        self.full_clean()
        
        # Update status dates
        if self.status == 'paid' and not self.paid_date:
            from django.utils import timezone
            self.paid_date = timezone.now()
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Bill {self.bill_number} - {self.business.business_name} ({self.billing_year})"
    
    @classmethod
    def can_generate_bill(cls, business, year):
        """
        Check if a bill can be generated for a business in a given year
        Returns (can_generate: bool, reason: str)
        """
        existing_bill = cls.objects.filter(
            business=business,
            billing_year=year,
            is_deleted=False
        ).exclude(status='cancelled')
        
        if existing_bill.exists():
            bill = existing_bill.first()
            return False, f"A bill already exists for {business.business_name} for the year {year}. Bill Number: {bill.bill_number}, Status: {bill.get_status_display()}"
        
        return True, "Bill can be generated"
    
    @classmethod
    def get_business_bills(cls, business):
        """
        Get all bills for a business, ordered by year (newest first)
        """
        return cls.objects.filter(
            business=business,
            is_deleted=False
        ).order_by('-billing_year', '-generated_date')
    
    @classmethod
    def get_current_year_bill(cls, business):
        """
        Get the bill for the current year for a business
        """
        from django.utils import timezone
        current_year = timezone.now().year
        return cls.objects.filter(
            business=business,
            billing_year=current_year,
            is_deleted=False
        ).exclude(status='cancelled').first()
    

    def record_click(self, link_type, request):
        """Record a payment link click"""
        self.last_clicked_at = timezone.now()
        self.click_count = (self.click_count or 0) + 1
        
        # Create click record
        click = PaymentLinkClick.objects.create(
            bill_type='business',
            business_bill=self,
            link_type=link_type,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            referer=request.META.get('HTTP_REFERER', '')[:500],
            session_id=request.session.session_key or ''
        )
        
        self.last_click_ip = click.ip_address
        self.save()
        return click
    
    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip







    # models.py - Add these models

class PaymentProvider(models.Model):
    """Store payment provider configuration"""
    name = models.CharField(max_length=100)
    provider_type = models.CharField(max_length=50, choices=[
        ('kowri', 'Kowri'),
        ('other', 'Other'),
    ])
    api_base_url = models.URLField()
    api_key = models.CharField(max_length=500)
    api_secret = models.CharField(max_length=500, blank=True)
    webhook_secret = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    config = models.JSONField(default=dict, blank=True)  # Additional config
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.provider_type})"

class PaymentTransaction(models.Model):
    """Track payment transactions"""
    TRANSACTION_STATUS = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    
    BILL_TYPES = (
        ('property', 'Property Tax'),
        ('business', 'Business Permit'),
    )
    
    transaction_id = models.CharField(max_length=100, unique=True)
    bill_type = models.CharField(max_length=20, choices=BILL_TYPES)
    
    # Polymorphic bill reference
    property_bill = models.ForeignKey('Bill', on_delete=models.SET_NULL, null=True, blank=True, related_name='payments_property')
    business_bill = models.ForeignKey('BopsBills', on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    provider = models.ForeignKey(PaymentProvider, on_delete=models.PROTECT)
    provider_transaction_id = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS, default='pending')
    
    # Payer information
    payer_name = models.CharField(max_length=200, blank=True)
    payer_phone = models.CharField(max_length=20, blank=True)
    payer_email = models.EmailField(blank=True)
    
    # Payment details
    payment_method = models.CharField(max_length=50, blank=True)  # USSD, Mobile Money, Card, etc.
    payment_channel = models.CharField(max_length=50, blank=True)  # Kowri App, Bank, etc.
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    # Timestamps
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['transaction_id']),
            models.Index(fields=['provider_transaction_id']),
            models.Index(fields=['bill_type', 'property_bill']),
            models.Index(fields=['bill_type', 'business_bill']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        bill_ref = self.property_bill or self.business_bill
        return f"{self.transaction_id} - {bill_ref} - {self.amount}"

class PaymentNotification(models.Model):
    """Log incoming payment notifications from provider"""
    transaction = models.ForeignKey(PaymentTransaction, on_delete=models.CASCADE, related_name='notifications')
    provider = models.ForeignKey(PaymentProvider, on_delete=models.PROTECT)
    raw_data = models.JSONField()
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']



class PaymentLinkClick(models.Model):
    """Track when users click on payment links"""
    LINK_TYPES = (
        ('web', 'Web Link'),
        ('ussd', 'USSD Code'),
        ('qr', 'QR Code'),
        ('direct', 'Direct Link'),
    )
    
    # Bill reference (polymorphic)
    bill_type = models.CharField(max_length=20, choices=PaymentTransaction.BILL_TYPES)
    property_bill = models.ForeignKey('Bill', on_delete=models.CASCADE, null=True, blank=True, related_name='link_clicks')
    business_bill = models.ForeignKey('BopsBills', on_delete=models.CASCADE, null=True, blank=True, related_name='link_clicks')
    
    # Click details
    link_type = models.CharField(max_length=20, choices=LINK_TYPES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    referer = models.URLField(blank=True, max_length=500)
    
    # Session tracking
    session_id = models.CharField(max_length=100, blank=True)
    
    # Timestamp
    clicked_at = models.DateTimeField(auto_now_add=True)
    
    # Payment tracking - if they eventually paid
    payment = models.ForeignKey('PaymentTransaction', on_delete=models.SET_NULL, null=True, blank=True, related_name='link_clicks')
    
    class Meta:
        ordering = ['-clicked_at']
        indexes = [
            models.Index(fields=['bill_type', 'property_bill']),
            models.Index(fields=['bill_type', 'business_bill']),
            models.Index(fields=['clicked_at']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        bill = self.property_bill or self.business_bill
        return f"Click on {self.link_type} for {bill} at {self.clicked_at}"


# class BopsBills(TimeStampModel):
#     bop = models.ForeignKey(Bops, on_delete=models.CASCADE)
#     bill_number = models.CharField(max_length=100, unique=True, db_column='Bill_Number', verbose_name='Bill Number' )
#     bill_date = models.DateField(db_column='Bill_Date', verbose_name='Bill Date')
#     bill_amount = models.DecimalField(max_digits=12, decimal_places=2, db_column='Bill_Amount', verbose_name='Bill Amount')
#     bill_status = models.CharField(max_length=100, choices=Bill.BILL_STATUS_CHOICES, db_column='Bill_Status', verbose_name='Bill Status')
#     bill_created_at = models.DateTimeField(auto_now_add=True, db_column='Bill_Created_At', verbose_name='Bill Created At')
#     bill_updated_at = models.DateTimeField(auto_now=True, db_column='Bill_Updated_At', verbose_name='Bill Updated At')
#     bill_created_by = models.ForeignKey(User, on_delete=models.PROTECT, db_column='Bill_Created_By', verbose_name='Bill Created By')
#     bill_updated_by = models.ForeignKey(User, on_delete=models.PROTECT, db_column='Bill_Updated_By', verbose_name='Bill Updated By')
#     bill_deleted_at = models.DateTimeField(blank=True, null=True, db_column='Bill_Deleted_At', verbose_name='Bill Deleted At')
#     bill_deleted_by = models.ForeignKey(User, on_delete=models.PROTECT, blank=True, null=True, db_column='Bill_Deleted_By', verbose_name='Bill Deleted By')