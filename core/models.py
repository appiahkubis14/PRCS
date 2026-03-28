# api/models.py - Fixed with proper integer primary keys

import uuid
from datetime import date
from decimal import Decimal

from django.db import models
from django.contrib.gis.db import models as gis_models
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point


# ============================================================
# Enums (PostgreSQL ENUM types)
# ============================================================

# class BillStatus(models.TextChoices):
#     UNPAID  = 'unpaid',  'Unpaid'
#     PARTIAL = 'partial', 'Partial'
#     PAID    = 'paid',    'Paid'
#     OVERDUE = 'overdue', 'Overdue'
#     GENERATED = 'generated', 'Generated'
class BillStatus(models.TextChoices):
    GENERATED = 'generated', 'Generated'
    SENT = 'sent', 'Sent'  # Add this line
    PAID = 'paid', 'Paid'
    UNPAID = 'unpaid', 'Unpaid'
    OVERDUE = 'overdue', 'Overdue'
    CANCELLED = 'cancelled', 'Cancelled'
    PARTIALLY_PAID = 'partially_paid', 'Partially Paid'
    # Add other statuses as needed


class BillType(models.TextChoices):
    PR  = 'pr',  'Property Register'
    BOP = 'bop', 'Business Operating Permit'


class EntryStatus(models.TextChoices):
    PENDING  = 'pending',  'Pending'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'


class PaymentStatus(models.TextChoices):
    PENDING  = 'pending',  'Pending'
    SUCCESS  = 'success',  'Success'
    FAILED   = 'failed',   'Failed'
    REVERSED = 'reversed', 'Reversed'


class PolygonStatus(models.TextChoices):
    UNASSESSED = 'unassessed', 'Unassessed'
    COMPLETE   = 'complete',   'Complete'
    PARTIAL    = 'partial',    'Partial'
    PASSED     = 'passed',     'Passed'
    DRAFT      = 'draft',      'Draft'
    ASSESSED   = 'assessed',   'Assessed'


class SessionStatus(models.TextChoices):
    PENDING  = 'pending',  'Pending'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'


class UserModelRole(models.TextChoices):
    ADMIN      = 'admin',      'Admin'
    SUPERVISOR = 'supervisor', 'Supervisor'
    COLLECTOR  = 'collector',  'Collector'
    CLIENT     = 'client',     'Client'


# ============================================================
# UserModel
# ============================================================

# class UserModel(models.Model):
#     """
#     Staff / collector accounts.
#     `user` links to Django's auth_user for authentication.
#     `supervisor` is a self-FK so collectors can be assigned to a supervisor.
#     """
#     user       = models.OneToOneField(
#                      User,
#                      on_delete=models.CASCADE,
#                      related_name='profile',
#                      db_column='user_id',
#                  )
#     employee_id = models.CharField(max_length=20, unique=True)
#     name        = models.CharField(max_length=100)
#     email       = models.CharField(max_length=100, unique=True)
#     phone       = models.CharField(max_length=20, blank=True, null=True)
#     password_hash = models.CharField(max_length=255, blank=True, null=True)
#     passwords = models.CharField(max_length=255, blank=True, null=True,default='P@ssw0rd24')
#     role        = models.CharField(
#                      max_length=20,
#                      choices=UserModelRole.choices,
#                      default=UserModelRole.COLLECTOR,
#                  )
#     supervisor  = models.ForeignKey(
#                      'self',
#                      on_delete=models.SET_NULL,
#                      null=True, blank=True,
#                      related_name='subordinates',
#                      db_column='supervisor_id',
#                  )
#     is_active   = models.BooleanField(default=True)
#     created_at  = models.DateTimeField(auto_now_add=True)
#     updated_at  = models.DateTimeField(auto_now=True)
#     expo_push_token = models.CharField(max_length=100, blank=True, null=True)

#     class Meta:
#         db_table = 'UserModels'

#     def __str__(self):
#         return f"{self.name} ({self.email})"

#     # ----------------------------------------------------------
#     # Password helpers
#     # ----------------------------------------------------------
#     @property
#     def password(self):
#         return self.password_hash

#     @password.setter
#     def password(self, value):
#         from django.contrib.auth.hashers import make_password
#         self.password_hash = make_password(value)

#     def check_password(self, raw_password):
#         from django.contrib.auth.hashers import check_password
#         return check_password(raw_password, self.password_hash)

# core/models.py - Add is_authenticated property to UserModel
# core/models.py - Update UserModel

class UserModel(models.Model):
    """
    Staff / collector accounts.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        db_column='user_id',
    )
    employee_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    email = models.CharField(max_length=100, unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    password_hash = models.CharField(max_length=255, blank=True, null=True)
    password_new = models.CharField(max_length=255, blank=True, null=True,default='P@ssw0rd24')
    role = models.CharField(
        max_length=20,
        choices=UserModelRole.choices,
        default=UserModelRole.COLLECTOR,
    )
    supervisor = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='subordinates',
        db_column='supervisor_id',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expo_push_token = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'UserModels'

    def __str__(self):
        return f"{self.name} ({self.email})"
    
    # Add these as properties (read-only)
    @property
    def is_authenticated(self):
        """Required for DRF permission classes"""
        return True
    
    @property
    def is_anonymous(self):
        """Required for DRF permission classes"""
        return False
    
    # ----------------------------------------------------------
    # Password helpers
    # ----------------------------------------------------------
    @property
    def password(self):
        return self.password_hash

    @password.setter
    def password(self, value):
        from django.contrib.auth.hashers import make_password
        self.password_hash = make_password(value)

    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password_hash)

# ============================================================
# Polygon / Property
# ============================================================

class Polygon(models.Model):
    """Spatial property polygon."""
    division    = models.IntegerField(default=0,null=True,blank=True)
    block       = models.IntegerField(default=0, null=True,blank=True)
    property    = models.IntegerField(default=0, null=True,blank=True)
    g_code      = models.CharField(max_length=100, blank=True, null=True,unique=True)
    area_in_me  = models.FloatField(default=0)
    district    = models.CharField(max_length=100, blank=True, null=True)
    postcode    = models.CharField(max_length=100, blank=True, null=True)   
    nlat        = models.FloatField(default=0)
    slat        = models.FloatField(default=0)
    wlong       = models.FloatField(default=0)
    elong       = models.FloatField(default=0)
    gpsname     = models.CharField(max_length=100, blank=True, null=True)
    region      = models.CharField(max_length=100, blank=True, null=True)
    area        = models.CharField(max_length=100, blank=True, null=True)
    addressv1   = models.CharField(max_length=100, blank=True, null=True)
    street      = models.CharField(max_length=100, blank=True, null=True)
    latitude    = models.FloatField(default=0)
    longitude   = models.FloatField(default=0)
    address     = models.CharField(max_length=100, blank=True, null=True)
    coordinates = models.JSONField(default=list)
    location    = models.CharField(max_length=100, blank=True, null=True)
    coordinates = models.JSONField(default=list)
    latitude    = models.FloatField(default=0)
    longitude   = models.FloatField(default=0)
    status      = models.CharField(
                     max_length=20,
                     choices=PolygonStatus.choices,
                     default=PolygonStatus.UNASSESSED,
                     null=True, blank=True
                 )
    assigned_to_user = models.ForeignKey(
                     UserModel,
                     on_delete=models.SET_NULL,
                     null=True, blank=True,
                     related_name='assessments',
                     db_column='assessed_to_user_id',
                 )
    accessed    = models.BooleanField(default=False, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    geom        = gis_models.GeometryField(null=True, blank=True, srid=4326)

    class Meta:
        db_table = 'polygons'

    def __str__(self):
        return f"Polygon {self.id} (div={self.division} blk={self.block})"


class Assignment(models.Model):
    """Links a collector to a polygon for data collection."""
    collector   = models.ForeignKey(
                     UserModel,
                     on_delete=models.CASCADE,
                     related_name='assignments',
                     db_column='collector_id',
                 )
    polygon     = models.ForeignKey(
                     Polygon,
                     on_delete=models.CASCADE,
                     related_name='assignments',
                     db_column='polygon_id',
                 )
    assigned_by = models.ForeignKey(
                     UserModel,
                     on_delete=models.CASCADE,
                     related_name='assignments_created',
                     db_column='assigned_by',
                 )
    assigned_at = models.DateTimeField(auto_now_add=True)
    status      = models.CharField(max_length=20, default='active')

    class Meta:
        db_table = 'assignments'


# ============================================================
# Session
# ============================================================

class Session(models.Model):
    """
    A field data-collection session for one polygon by one collector.
    reviewed_by → the supervisor who approved/rejected it.
    """
    polygon      = models.ForeignKey(
                      Polygon,
                      on_delete=models.CASCADE,
                      related_name='sessions',
                      db_column='polygon_id',
                  )
    collector    = models.ForeignKey(
                      UserModel,
                      on_delete=models.CASCADE,
                      related_name='sessions',
                      db_column='collector_id',
                  )
    pr_data      = models.JSONField(null=True, blank=True)
    businesses   = models.JSONField(default=list)
    status       = models.CharField(
                      max_length=20,
                      choices=SessionStatus.choices,
                      default=SessionStatus.PENDING,
                  )
    reviewed_by  = models.ForeignKey(
                      UserModel,
                      on_delete=models.SET_NULL,
                      null=True, blank=True,
                      related_name='reviewed_sessions',
                      db_column='reviewed_by',
                  )
    reviewed_at   = models.DateTimeField(null=True, blank=True)
    review_notes  = models.TextField(null=True, blank=True)
    submitted_at  = models.DateTimeField(auto_now_add=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)
    deleted_at    = models.DateTimeField(null=True, blank=True)

    # Location capture at time of submission
    location_status    = models.CharField(max_length=20, null=True, blank=True)
    location_lat       = models.FloatField(null=True, blank=True)
    location_lng       = models.FloatField(null=True, blank=True)
    location_accuracy  = models.FloatField(null=True, blank=True)
    location_timestamp = models.DateTimeField(null=True, blank=True)
    location_mocked    = models.BooleanField(null=True, blank=True)
    location_distance  = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = 'sessions'

    def compute_status(self):
        pr_entries  = self.pr_entries.filter(deleted_at__isnull=True)
        bop_entries = self.bop_entries.filter(deleted_at__isnull=True)
        all_entries = list(pr_entries) + list(bop_entries)

        if not all_entries:
            return SessionStatus.PENDING

        statuses = [e.status for e in all_entries]

        if all(s == EntryStatus.APPROVED for s in statuses):
            return SessionStatus.APPROVED
        elif any(s == EntryStatus.REJECTED for s in statuses):
            return SessionStatus.REJECTED
        return SessionStatus.PENDING

    def update_status(self):
        self.status = self.compute_status()
        self.save(update_fields=['status', 'updated_at'])


    def __str__(self):
        return f"Session {self.id} ({self.status} by {self.collector})"


class PREntry(models.Model):
    """A single property-rate data entry within a session."""
    session      = models.ForeignKey(
                      Session,
                      on_delete=models.CASCADE,
                      related_name='pr_entries',
                      db_column='session_id',
                  )
    entry_index  = models.IntegerField()
    mode         = models.CharField(max_length=100)
    data         = models.JSONField()
    status       = models.CharField(
                      max_length=20,
                      choices=EntryStatus.choices,
                      default=EntryStatus.PENDING,
                  )
    reviewed_by  = models.ForeignKey(
                      UserModel,
                      on_delete=models.SET_NULL,
                      null=True, blank=True,
                      related_name='reviewed_pr_entries',
                      db_column='reviewed_by',
                  )
    reviewed_at  = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(null=True, blank=True)
    revision_of  = models.UUIDField(null=True, blank=True)  
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    deleted_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'pr_entries'
        unique_together = [['session', 'entry_index']]


class BOPEntry(models.Model):
    """A single business-operating-permit data entry within a session."""
    session      = models.ForeignKey(
                      Session,
                      on_delete=models.CASCADE,
                      related_name='bop_entries',
                      db_column='session_id',
                  )
    entry_index  = models.IntegerField()
    mode         = models.CharField(max_length=100)
    data         = models.JSONField()
    status       = models.CharField(
                      max_length=20,
                      choices=EntryStatus.choices,
                      default=EntryStatus.PENDING,
                  )
    reviewed_by  = models.ForeignKey(
                      UserModel,
                      on_delete=models.SET_NULL,
                      null=True, blank=True,
                      related_name='reviewed_bop_entries',
                      db_column='reviewed_by',
                  )
    reviewed_at  = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(null=True, blank=True)
    revision_of  = models.UUIDField(null=True, blank=True)   # UUID of previous version, not a FK
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    deleted_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'bop_entries'
        unique_together = [['session', 'entry_index']]



# ============================================================
# Business classification hierarchy
# BusinessType → BusinessSubType → BusinessCategory
# ============================================================

class BusinessType(models.Model):
    slug       = models.CharField(max_length=150, unique=True)
    name       = models.CharField(max_length=200)
    coa_code   = models.CharField(max_length=20)
    duration   = models.CharField(max_length=30, default='Per Annum')
    is_active  = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'business_types'

    def __str__(self):
        return self.name


class BusinessSubType(models.Model):
    business_type = models.ForeignKey(
                       BusinessType,
                       on_delete=models.CASCADE,
                       related_name='sub_types',
                       db_column='business_type_id',
                   )
    slug          = models.CharField(max_length=150)
    name          = models.CharField(max_length=200)
    sort_order    = models.IntegerField(default=0)
    is_active     = models.BooleanField(default=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'business_sub_types'
        unique_together = [['business_type', 'slug']]

    def __str__(self):
        return self.name


class BusinessCategory(models.Model):
    business_type = models.ForeignKey(
                       BusinessType,
                       on_delete=models.CASCADE,
                       related_name='categories',
                       db_column='business_type_id',
                   )
    sub_type      = models.ForeignKey(
                       BusinessSubType,
                       on_delete=models.CASCADE,
                       null=True, blank=True,
                       related_name='categories',
                       db_column='sub_type_id',
                   )
    slug           = models.CharField(max_length=150)
    label          = models.CharField(max_length=200)
    amount         = models.DecimalField(max_digits=12, decimal_places=2)
    sort_order     = models.IntegerField(default=0)
    is_active      = models.BooleanField(default=True)
    effective_from = models.DateField(default=date.today)
    effective_to   = models.DateField(null=True, blank=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'business_categories'
        unique_together = [['business_type', 'slug']]

    def __str__(self):
        return self.label




# ============================================================
# Business (legacy imported data)
# ============================================================
class Business(models.Model):
    account_number          = models.CharField(max_length=100, unique=True)
    business_name           = models.CharField(max_length=255)
    business_category       = models.TextField(blank=True, null=True)
    business_class          = models.TextField(blank=True, null=True)
    owner_name              = models.CharField(max_length=255, blank=True, null=True)
    email                   = models.EmailField(max_length=255, blank=True, null=True)
    business_email          = models.EmailField(max_length=255, blank=True, null=True)  # Added from Bops
    phone_number            = models.CharField(max_length=50, blank=True, null=True)
    phone_number_primary    = models.CharField(max_length=50, blank=True, null=True)
    house_number            = models.CharField(max_length=100, blank=True, null=True)
    digital_address         = models.CharField(max_length=100, blank=True, null=True)
    location                = models.CharField(max_length=255, blank=True, null=True)
    street_name             = models.CharField(max_length=255, blank=True, null=True)
    address                 = models.TextField(blank=True, null=True)
    structure_id            = models.CharField(max_length=50, blank=True, null=True)
    centroid                = models.CharField(max_length=100, blank=True, null=True)
    block                   = models.CharField(max_length=50, blank=True, null=True)
    division                = models.CharField(max_length=50, blank=True, null=True)
    lng                     = models.DecimalField(max_digits=15, decimal_places=12, blank=True, null=True)
    lat                     = models.DecimalField(max_digits=15, decimal_places=12, blank=True, null=True)
    geometry                = gis_models.GeometryField(null=True, blank=True, srid=4326)
    flat_rate               = models.DecimalField(max_digits=100, decimal_places=2, blank=True, null=True)
    business_type           = models.ForeignKey(
                                 BusinessType,
                                 on_delete=models.SET_NULL,
                                 null=True, blank=True,
                                 related_name='businesses',
                                 db_column='business_type_id',
                              )
    business_sub_type       = models.ForeignKey(
                                 BusinessSubType,
                                 on_delete=models.SET_NULL,
                                 null=True, blank=True,
                                 related_name='businesses',
                                 db_column='business_sub_type_id',
                              )
    business_category_value = models.ForeignKey(
                                 BusinessCategory,
                                 on_delete=models.SET_NULL,
                                 null=True, blank=True,
                                 related_name='businesses',
                                 db_column='business_category_id',
                              )
    source_sheet            = models.CharField(max_length=100, blank=True, null=True)
    is_deleted              = models.BooleanField(default=False)
    deleted_at              = models.DateTimeField(null=True, blank=True)
    created_at              = models.DateTimeField(auto_now_add=True)
    updated_at              = models.DateTimeField(auto_now=True)
    
    # Optional tracking fields for Bops import
    imported_from_bops      = models.BooleanField(default=False)
    bops_import_date        = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'businesses'

    def __str__(self):
        return self.business_name
    
    def save(self, *args, **kwargs):
        # Only calculate geom if geom is not set AND we have valid coordinates
        if not self.geometry:
            try:
                # Check if both lng and lat have valid values
                if self.lng is not None and self.lat is not None:
                    # Convert to float to ensure they're numeric
                    lon = float(self.lng)
                    lat = float(self.lat)
                    
                    # Validate that coordinates are within reasonable ranges
                    # Latitude: -90 to 90, Longitude: -180 to 180
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        self.geometry = Point(lon, lat, srid=4326)
                    else:
                        # Log invalid coordinates but don't crash
                        print(f"Invalid coordinates for {self.business_name}: lat={lat}, lon={lon}")
                else:
                    # Try to parse from centroid if available and coordinates are missing
                    if self.centroid:
                        try:
                            # Handle different centroid formats
                            # Common formats: "lat,lon", "lat lon", "POINT(lon lat)", etc.
                            centroid_str = str(self.centroid).strip()
                            
                            # Check if it's in POINT format
                            if centroid_str.upper().startswith('POINT'):
                                # Extract coordinates from POINT(lon lat)
                                coords = centroid_str.replace('POINT', '').replace('(', '').replace(')', '').strip().split()
                                if len(coords) == 2:
                                    lon = float(coords[0])
                                    lat = float(coords[1])
                                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                                        self.geometry = Point(lon, lat, srid=4326)
                            
                            # Check if it's in "lat,lon" format
                            elif ',' in centroid_str:
                                parts = centroid_str.split(',')
                                if len(parts) == 2:
                                    lat = float(parts[0].strip())
                                    lon = float(parts[1].strip())
                                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                                        self.geometry = Point(lon, lat, srid=4326)
                            
                            # Check if it's in "lat lon" format
                            elif ' ' in centroid_str:
                                parts = centroid_str.split()
                                if len(parts) == 2:
                                    lat = float(parts[0].strip())
                                    lon = float(parts[1].strip())
                                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                                        self.geometry = Point(lon, lat, srid=4326)
                        except (ValueError, AttributeError) as e:
                            # Log parsing error but don't crash
                            print(f"Error parsing centroid for {self.business_name}: {e}")
                            
            except (ValueError, TypeError) as e:
                # Log the error but don't prevent saving
                print(f"Error creating Point for {self.business_name}: {e}")
                # You might want to use Django's logger instead
                # logger.warning(f"Error creating Point for {self.business_name}: {e}")
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account_number} - {self.business_name}"


# ============================================================
# Bill & Payment
# ============================================================

class Bill(models.Model):
    """
    Financial bill issued against a session/polygon.
    issued_by → the staff member who generated the bill.
    """
    bill_number   = models.CharField(max_length=30, unique=True)
    session       = models.ForeignKey(
                       Session,
                       null=True,
                       blank=True,
                       on_delete=models.CASCADE,
                       related_name='bills',
                       db_column='session_id',
                   )
    business = models.ForeignKey(
        Business, 
        on_delete=models.CASCADE, 
        related_name='bills',
        verbose_name='Business',
        null=True,
        blank=True
    )
    polygon       = models.ForeignKey(
                       Polygon,
                       null=True,
                       blank=True,
                       on_delete=models.CASCADE,
                       related_name='bills',
                       db_column='polygon_id',
                   )
    billing_year  = models.IntegerField(default=0)
    bill_type     = models.CharField(max_length=100, choices=BillType.choices, null=True, blank=True)
    owner_name    = models.CharField(max_length=100, null=True, blank=True)
    owner_contact = models.CharField(max_length=20, null=True, blank=True)
    owner_email   = models.CharField(max_length=100, null=True, blank=True)
    amount        = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    arrears       = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_due     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_paid   = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_date      = models.DateField()
    status        = models.CharField(
                       max_length=20,
                       choices=BillStatus.choices,
                       verbose_name='Status',
                       default=BillStatus.UNPAID
                   )
    tax_amount    = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    penalty_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    added_by      = models.ForeignKey(
                      User,
                       on_delete=models.SET_NULL,
                       null=True, blank=True,
                       related_name='added_bills',
                       
    )
    issued_by     = models.ForeignKey(
                       UserModel,
                       on_delete=models.SET_NULL,
                       null=True, blank=True,
                       related_name='issued_bills',
                       db_column='issued_by',
                   )
    issued_at     = models.DateTimeField(auto_now_add=True)
    sent_date     = models.DateTimeField(null=True, blank=True)
    deleted_at    = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True, verbose_name='Notes')

     # Add these new fields for tracking
    last_clicked_at = models.DateTimeField(null=True, blank=True, verbose_name='Last Link Clicked')
    click_count = models.IntegerField(default=0, verbose_name='Number of Link Clicks')
    last_click_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='Last Click IP')

    class Meta:
        db_table = 'bills'

    def __str__(self):
        return f"{self.bill_number} ({self.status})"

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
            if BopsBills.objects.filter(bill_number=bill_number, ).exists():
                # If somehow the number exists, try next
                next_number += 1
                bill_number = f"{prefix}{next_number:04d}"
            
            return bill_number
    
    def save(self, *args, **kwargs):
        """
        Override save to run validation, auto-generate bill number, and auto-calculate total
        """
        # Check if we're only updating specific fields (like click tracking)
        update_fields = kwargs.get('update_fields', None)
        
        # Auto-generate bill number if not provided or empty
        if not self.bill_number or self.bill_number.strip() == '':
            self.bill_number = self.generate_bill_number()
        
        # Auto-calculate total if not set or if components changed
        if not self.total_amount or kwargs.get('force_recalculate', False):
            self.total_amount = self.tax_amount - self.discount_amount + self.penalty_amount
        
        # Only run full validation if we're not just updating click tracking fields
        if update_fields is None or not all(field in update_fields for field in ['last_clicked_at', 'click_count', 'last_click_ip']):
            # Run full validation for normal saves
            self.full_clean()
        else:
            # Skip validation for click tracking updates to avoid status validation errors
            # But still validate required fields
            from django.core.exceptions import ValidationError
            if not self.bill_number:
                raise ValidationError({'bill_number': 'Bill number is required'})
            if not self.billing_year:
                raise ValidationError({'billing_year': 'Billing year is required'})
        
        # Update status dates
        if hasattr(self, 'paid_date') and self.status == 'paid' and not self.paid_date:
            from django.utils import timezone
            self.paid_date = timezone.now()
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Bill {self.bill_number} - ({self.billing_year})"
    
    @classmethod
    def can_generate_bill(cls, business, year):
        """
        Check if a bill can be generated for a business in a given year
        Returns (can_generate: bool, reason: str)
        """
        existing_bill = cls.objects.filter(
            business=business,
            billing_year=year,
            
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
            
        ).order_by('-billing_year', '-issued_date')
    
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
            
        ).exclude(status='cancelled').first()
    

    def record_click(self, link_type, request):
        """Record a payment link click"""
        from django.utils import timezone
        from django.db.models import F
        
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Create click record
        click = PaymentLinkClick.objects.create(
            bill=self,
            bill_type='bop',
            link_type=link_type,
            ip_address=ip,
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            referer=request.META.get('HTTP_REFERER', '')[:500],
            session_id=request.session.session_key or ''
        )
        
        # Update the bill's click tracking fields using update() to bypass save() validation
        # This avoids calling full_clean() which validates status
        from core.models import BopsBills  # Import here to avoid circular imports
        
        updated_count = BopsBills.objects.filter(id=self.id).update(
            last_clicked_at=timezone.now(),
            click_count=F('click_count') + 1,
            last_click_ip=ip
        )
        
        if updated_count > 0:
            # Refresh the instance from database
            self.refresh_from_db()
            print(f"Bill {self.bill_number} click_count updated to {self.click_count}")
        else:
            print(f"Failed to update click tracking for bill {self.bill_number}")
        
        return click
        
    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    


class Payment(models.Model):
    """
    A payment made against a bill.
    reconciled_by → staff who reconciled it.
    recorded_by   → staff who recorded it.
    """
    bill           = models.ForeignKey(
                        Bill,
                        on_delete=models.CASCADE,
                        related_name='payments',
                        db_column='bill_id',
                    )
    amount         = models.DecimalField(max_digits=12, decimal_places=2)
    method         = models.CharField(max_length=30)
    reference      = models.CharField(max_length=100, null=True, blank=True)
    hubtel_data    = models.JSONField(null=True, blank=True)
    receipt_number = models.CharField(max_length=30, null=True, blank=True)
    status         = models.CharField(
                        max_length=20,
                        choices=PaymentStatus.choices,
                        default=PaymentStatus.PENDING,
                    )
    reconciled     = models.BooleanField(default=False)
    reconciled_at  = models.DateTimeField(null=True, blank=True)
    reconciled_by  = models.ForeignKey(
                        UserModel,
                        on_delete=models.SET_NULL,
                        null=True, blank=True,
                        related_name='reconciled_payments',
                        db_column='reconciled_by',
                    )
    recorded_by    = models.ForeignKey(
                        UserModel,
                        on_delete=models.SET_NULL,
                        null=True, blank=True,
                        related_name='recorded_payments',
                        db_column='recorded_by',
                    )
    paid_at        = models.DateTimeField(auto_now_add=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    deleted_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'payments'

    def __str__(self):
        return f"Payment {self.id} – {self.amount} ({self.status})"


# ============================================================
# Notifications
# ============================================================

class CollectorNotification(models.Model):
    """
    In-app / push notifications sent to collectors.
    recipient → the UserModel being notified.
    """
    recipient = models.ForeignKey(          # renamed from 'UserModel' to avoid collision
                   UserModel,
                   on_delete=models.CASCADE,
                   related_name='notifications',
                   db_column='UserModel_id',
                   null=True, blank=True,
               )
    type      = models.CharField(max_length=20)
    title     = models.CharField(max_length=200)
    body      = models.TextField()
    entity_id = models.CharField(max_length=50, null=True, blank=True)
    read      = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'collector_notifications'
        ordering = ['-created_at']


class Notification(models.Model):
    """
    External notifications (SMS, email) sent to bill owners.
    bill → the bill this notification relates to (nullable for system-wide messages).
    """
    bill      = models.ForeignKey(
                   Bill,
                   on_delete=models.CASCADE,
                   null=True, blank=True,
                   related_name='notifications',
                   db_column='bill_id',
               )
    type      = models.CharField(max_length=20)
    channel   = models.CharField(max_length=20)
    recipient = models.CharField(max_length=100)
    message   = models.TextField(null=True, blank=True)
    status    = models.CharField(max_length=20, default='pending')
    sent_at   = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'


# ============================================================
# OTP
# ============================================================

class OTPCode(models.Model):
    """One-time password codes for email verification / login."""
    email      = models.CharField(max_length=100)
    code_hash  = models.CharField(max_length=255)
    attempts   = models.IntegerField(default=0)
    expires_at = models.DateTimeField()
    used       = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'otp_codes'
        indexes  = [
            models.Index(fields=['email']),
            models.Index(fields=['expires_at']),
        ]


# ============================================================
# Lookup tables
# ============================================================

class LookupGroup(models.Model):
    """Top-level category for lookup values (e.g. 'property_use', 'zone_type')."""
    slug           = models.CharField(max_length=50, unique=True)
    label          = models.CharField(max_length=100)
    allows_custom  = models.BooleanField(default=False)
    sort_order     = models.IntegerField(default=0)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lookup_groups'
        ordering = ['sort_order']


class LookupValue(models.Model):
    """An option within a LookupGroup."""
    group      = models.ForeignKey(
                    LookupGroup,
                    on_delete=models.CASCADE,
                    related_name='values',
                    db_column='group_id',
                )
    slug       = models.CharField(max_length=100)
    label      = models.CharField(max_length=150)
    sort_order = models.IntegerField(default=0)
    is_active  = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lookup_values'
        unique_together = [['group', 'slug']]


# ============================================================
# System Settings
# ============================================================

class SystemSetting(models.Model):
    """Key/value system configuration. updated_by → admin who last changed it."""
    key        = models.CharField(max_length=100, primary_key=True)
    value      = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
                    UserModel,
                    on_delete=models.SET_NULL,
                    null=True, blank=True,
                    related_name='system_settings_updated',
                    db_column='updated_by',
                 )

    class Meta:
        db_table = 'system_settings'


# ============================================================
# Refresh Tokens
# ============================================================

class RefreshToken(models.Model):
    """JWT refresh tokens. user → the UserModel who owns this token."""
    user       = models.ForeignKey(          # renamed from 'UserModel' to avoid collision
                    UserModel,
                    on_delete=models.CASCADE,
                    related_name='refresh_tokens',
                    db_column='UserModel_id',  # keeps existing column name in DB
                 )
    token_hash = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'refresh_tokens'


# ============================================================
# Audit Log
# ============================================================

class AuditLog(models.Model):
    """Immutable audit trail. actor → the UserModel who performed the action."""
    actor       = models.ForeignKey(         # renamed from 'UserModel' to avoid collision
                     UserModel,
                     on_delete=models.SET_NULL,
                     null=True, blank=True,
                     related_name='audit_logs',
                     db_column='UserModel_id',  # keeps existing column name in DB
                  )
    action      = models.CharField(max_length=50)
    entity_type = models.CharField(max_length=30, null=True, blank=True)
    entity_id   = models.CharField(max_length=50, null=True, blank=True)
    details     = models.JSONField(null=True, blank=True)
    ip_address  = models.CharField(max_length=45, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_log'


# ============================================================
# Bank Statements
# ============================================================

class BankStatement(models.Model):
    """
    Imported bank statement lines for payment reconciliation.
    matched_payment → the Payment this line was matched to.
    uploaded_by     → the staff who uploaded the statement file.
    """
    bank_name       = models.CharField(max_length=50)
    statement_date  = models.DateField()
    description     = models.TextField(null=True, blank=True)
    reference       = models.CharField(max_length=100, null=True, blank=True)
    amount          = models.DecimalField(max_digits=12, decimal_places=2)
    matched_payment = models.ForeignKey(
                         Payment,
                         on_delete=models.SET_NULL,
                         null=True, blank=True,
                         related_name='bank_statements',
                         db_column='matched_payment_id',
                      )
    status          = models.CharField(max_length=20, default='unmatched')
    uploaded_by     = models.ForeignKey(
                         UserModel,
                         on_delete=models.SET_NULL,
                         null=True, blank=True,
                         related_name='uploaded_statements',
                         db_column='uploaded_by',
                      )
    uploaded_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bank_statements'


# ============================================================
# Fee Schedule
# ============================================================

class FeeSchedule(models.Model):
    """Billing fee rates per category/period. created_by → admin who set the rate."""
    bill_type    = models.CharField(max_length=100)
    category     = models.CharField(max_length=100)
    sub_category = models.CharField(max_length=100, null=True, blank=True)
    amount       = models.DecimalField(max_digits=12, decimal_places=2)
    effective_from = models.DateField()
    effective_to   = models.DateField(null=True, blank=True)
    created_by   = models.ForeignKey(
                      UserModel,
                      on_delete=models.SET_NULL,
                      null=True, blank=True,
                      related_name='fee_schedules_created',
                      db_column='created_by',
                   )
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fee_schedule'


# ============================================================
# Block Boundaries (GIS)
# ============================================================

class BlockBoundary(models.Model):
    """GIS boundary polygon for an administrative block."""
    id             = models.CharField(max_length=20, primary_key=True)
    division       = models.IntegerField()
    block          = models.IntegerField()
    property_count = models.IntegerField()
    complete_count = models.IntegerField()
    assessed_count = models.IntegerField()
    geom          = gis_models.GeometryField(null=True, blank=True, srid=4326)

    class Meta:
        db_table = 'block_boundaries'


# ============================================================
# Property Rates (imported valuation data)
# ============================================================

class PropertyRate(models.Model):
    """
    Imported property valuation records.
    polygon → the spatial polygon this valuation belongs to.
    """
    valuation_no   = models.CharField(max_length=30, unique=True)
    polygon        = models.ForeignKey(
                        Polygon,
                        on_delete=models.SET_NULL,
                        null=True, blank=True,
                        related_name='property_rates',
                        db_column='polygon_id',
                     )
    title          = models.CharField(max_length=20, null=True, blank=True)
    surname        = models.CharField(max_length=100, null=True, blank=True)
    first_name     = models.CharField(max_length=100, null=True, blank=True)
    mobile_number  = models.CharField(max_length=30, null=True, blank=True)
    prop_type      = models.CharField(max_length=50, null=True, blank=True)
    prop_name      = models.CharField(max_length=150, null=True, blank=True)
    prop_owner     = models.CharField(max_length=150, null=True, blank=True)
    house_no       = models.CharField(max_length=30, null=True, blank=True)
    suburb         = models.CharField(max_length=100, null=True, blank=True)
    division       = models.IntegerField(null=True, blank=True)
    block          = models.IntegerField(null=True, blank=True)
    street_name    = models.CharField(max_length=100, null=True, blank=True)
    area_zone      = models.CharField(max_length=100, null=True, blank=True)
    prop_address   = models.CharField(max_length=200, null=True, blank=True)
    landmark       = models.CharField(max_length=200, null=True, blank=True)
    rate_code      = models.DecimalField(max_digits=100, decimal_places=6, null=True, blank=True)
    rate_input     = models.DecimalField(max_digits=100, decimal_places=6, null=True, blank=True)
    rateable_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    total_amount   = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    current_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    tin_number     = models.CharField(max_length=50, null=True, blank=True)
    email          = models.CharField(max_length=100, null=True, blank=True)
    imported_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'property_rates'


# ============================================================
# Version Tracking
# ============================================================

class VersionTbl(models.Model):
    version    = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'version_tbl'


# ============================================================
# Payment Providers & Transactions
# ============================================================

class PaymentProvider(models.Model):
    """External payment gateway configuration (Hubtel, MTN MoMo, etc.)."""
    name           = models.CharField(max_length=100)
    provider_type  = models.CharField(max_length=50)
    api_base_url   = models.URLField()
    api_key        = models.CharField(max_length=500)
    api_secret     = models.CharField(max_length=500, blank=True)
    webhook_secret = models.CharField(max_length=500, blank=True)
    is_active      = models.BooleanField(default=True)
    config         = models.JSONField(default=dict, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payment_providers'

    def __str__(self):
        return self.name


class PaymentTransaction(models.Model):
    """
    A gateway-level payment transaction.
    bill     → the Bill being paid (proper FK — not a raw UUIDField).
    provider → which payment gateway processed it.
    """
    TRANSACTION_STATUS = (
        ('pending',   'Pending'),
        ('completed', 'Completed'),
        ('failed',    'Failed'),
        ('refunded',  'Refunded'),
    )

    transaction_id         = models.CharField(max_length=100, unique=True)
    bill                   = models.ForeignKey(      # ← proper FK replacing bill_id UUIDField
                                Bill,
                                on_delete=models.SET_NULL,
                                null=True, blank=True,
                                related_name='payment_transactions',
                                db_column='bill_id',
                             )
    amount                 = models.DecimalField(max_digits=12, decimal_places=2)
    provider               = models.ForeignKey(
                                PaymentProvider,
                                on_delete=models.PROTECT,
                                related_name='transactions',
                                db_column='provider_id',
                             )
    provider_transaction_id = models.CharField(max_length=200, blank=True)
    status                 = models.CharField(
                                max_length=20,
                                choices=TRANSACTION_STATUS,
                                default='pending',
                             )
    bill_type              = models.CharField(max_length=100, blank=True)
    payer_name             = models.CharField(max_length=200, blank=True)
    payer_phone            = models.CharField(max_length=20, blank=True)
    payer_email            = models.EmailField(blank=True)
    payment_method         = models.CharField(max_length=50, blank=True)
    payment_channel        = models.CharField(max_length=50, blank=True)
    metadata               = models.JSONField(default=dict, blank=True)
    error_message          = models.TextField(blank=True)
    initiated_at           = models.DateTimeField(auto_now_add=True)
    completed_at           = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'payment_transactions'
        ordering = ['-initiated_at']
        indexes  = [
            models.Index(fields=['transaction_id']),
            models.Index(fields=['provider_transaction_id']),
            models.Index(fields=['bill']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.transaction_id} – {self.amount}"


class PaymentNotification(models.Model):
    """
    Raw webhook payloads received from a payment provider.
    transaction → the PaymentTransaction this webhook relates to.
    provider    → which gateway sent it.
    """
    transaction  = models.ForeignKey(
                      PaymentTransaction,
                      on_delete=models.CASCADE,
                      related_name='notifications',
                      db_column='transaction_id',
                   )
    provider     = models.ForeignKey(
                      PaymentProvider,
                      on_delete=models.PROTECT,
                      related_name='notifications',
                      db_column='provider_id',
                   )
    raw_data     = models.JSONField()
    processed    = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    error        = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payment_notifications'


class PaymentLinkClick(models.Model):
    """
    Analytics: tracks every click on a payment link.
    bill    → the Bill the link was for (proper FK — not a raw UUIDField).
    payment → the PaymentTransaction that followed, if any.
    """
    LINK_TYPES = (
        ('web',    'Web Link'),
        ('ussd',   'USSD Code'),
        ('qr',     'QR Code'),
        ('direct', 'Direct Link'),
    )

    bill         = models.ForeignKey(        # ← proper FK replacing bill_id UUIDField
                      Bill,
                      on_delete=models.SET_NULL,
                      null=True, blank=True,
                      related_name='link_clicks',
                      db_column='bill_id',
                   )
    bill_type    = models.CharField(max_length=100, choices=BillType.choices, null=True, blank=True)
    link_type    = models.CharField(max_length=20, choices=LINK_TYPES)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    user_agent   = models.TextField(blank=True)        # renamed from UserModel_agent
    referer      = models.URLField(blank=True, max_length=500)
    session_id   = models.CharField(max_length=100, blank=True)
    clicked_at   = models.DateTimeField(auto_now_add=True)
    payment      = models.ForeignKey(
                      PaymentTransaction,
                      on_delete=models.SET_NULL,
                      null=True, blank=True,
                      related_name='link_clicks',
                      db_column='payment_transaction_id',
                   )

    class Meta:
        db_table = 'payment_link_clicks'
        indexes  = [
            models.Index(fields=['bill']),
            models.Index(fields=['clicked_at']),
            models.Index(fields=['session_id']),
        ]

    def __str__(self):
        return f"Click on {self.link_type} for bill {self.bill_id} at {self.clicked_at}"












#####################################################################################################################

class PropertyOwner(models.Model):
    """
    Stores property owner information collected during data collection.
    Links to a polygon (property) and can be associated with sessions.
    """
    # Title choices
    class Title(models.TextChoices):
        MR = 'Mr', 'Mr'
        MRS = 'Mrs', 'Mrs'
        MS = 'Ms', 'Ms'
        DR = 'Dr', 'Dr'
        CHIEF = 'Chief', 'Chief'
        NONE = 'None', 'None'

    # Property type choices
    class PropertyType(models.TextChoices):
        RESIDENTIAL = 'Residential', 'Residential'
        COMMERCIAL = 'Commercial', 'Commercial'
        INDUSTRIAL = 'Industrial', 'Industrial'
        MIXED_USE = 'Mixed Use', 'Mixed Use'
        VACANT_LAND = 'Vacant Land', 'Vacant Land'
        OTHER = 'Other', 'Other'

    # Property state choices
    class PropertyState(models.TextChoices):
        COMPLETED = 'Completed', 'Completed'
        UNDER_CONSTRUCTION = 'Under Construction', 'Under Construction'
        UNFINISHED = 'Unfinished', 'Unfinished'
        ABANDONED = 'Abandoned', 'Abandoned'
        RENOVATION = 'Under Renovation', 'Under Renovation'

    # Occupier type choices
    class OccupierType(models.TextChoices):
        OWNER_OCCUPIED = 'Owner Occupied', 'Owner Occupied'
        TENANT = 'Tenant', 'Tenant'
        VACANT = 'Vacant', 'Vacant'
        PARTIAL = 'Partially Occupied', 'Partially Occupied'

    # Communication method choices
    class CommunicationMethod(models.TextChoices):
        PHONE = 'Phone Call', 'Phone Call'
        SMS = 'SMS', 'SMS'
        EMAIL = 'Email', 'Email'
        WHATSAPP = 'WhatsApp', 'WhatsApp'
        IN_PERSON = 'In Person', 'In Person'

    # Payment method choices
    class PaymentMethod(models.TextChoices):
        MOBILE_MONEY = 'Mobile Money', 'Mobile Money'
        BANK_TRANSFER = 'Bank Transfer', 'Bank Transfer'
        CASH = 'Cash', 'Cash'
        CHEQUE = 'Cheque', 'Cheque'
        CARD = 'Card', 'Card'

    # Basic owner information
    title = models.CharField(max_length=20, choices=Title.choices, blank=True, null=True)
    owner_name = models.CharField(max_length=200, db_index=True)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    alternative_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(max_length=200, blank=True, null=True)
    ghana_card_number = models.CharField(max_length=30, blank=True, null=True, db_index=True)
    tin_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Location information
    location = models.CharField(max_length=255, blank=True, null=True)
    gps_location = models.CharField(max_length=100, blank=True, null=True)
    street_name = models.CharField(max_length=255, blank=True, null=True)
    house_number = models.CharField(max_length=100, blank=True, null=True)
    digital_address = models.CharField(max_length=100, blank=True, null=True)
    
    # Property details
    property_type = models.CharField(max_length=50, choices=PropertyType.choices, blank=True, null=True)
    property_state = models.CharField(max_length=50, choices=PropertyState.choices, blank=True, null=True)
    property_details = models.TextField(blank=True, null=True)
    rooms = models.CharField(max_length=10, blank=True, null=True)  # Can be "4" or "4+"
    occupier = models.CharField(max_length=50, choices=OccupierType.choices, blank=True, null=True)
    
    # Collection preferences
    communication_method = models.CharField(max_length=50, choices=CommunicationMethod.choices, blank=True, null=True)
    payment_method = models.CharField(max_length=50, choices=PaymentMethod.choices, blank=True, null=True)
    preferred_contact_time = models.CharField(max_length=100, blank=True, null=True)
    
    # Relationships
    polygon = models.ForeignKey(
        Polygon,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='property_owners',
        db_column='polygon_id',
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='property_owners',
        db_column='session_id',
    )
    collector = models.ForeignKey(
        UserModel,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='collected_property_owners',
        db_column='collector_id',
    )
    
    # Status and tracking
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        UserModel,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verified_property_owners',
        db_column='verified_by',
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'property_owners'
        indexes = [
            models.Index(fields=['owner_name']),
            models.Index(fields=['contact_number']),
            models.Index(fields=['polygon']),
            models.Index(fields=['session']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        name = self.owner_name
        if self.title:
            name = f"{self.title} {name}"
        if self.polygon:
            return f"{name} - Polygon {self.polygon.id}"
        return name
    
    def save(self, *args, **kwargs):
        # Auto-clean phone numbers
        if self.contact_number:
            self.contact_number = self.contact_number.strip()
        if self.alternative_number:
            self.alternative_number = self.alternative_number.strip()
        
        # Auto-format Ghana card number if present
        if self.ghana_card_number:
            self.ghana_card_number = self.ghana_card_number.upper().strip()
        
        super().save(*args, **kwargs)
    
    @classmethod
    def get_by_polygon(cls, polygon_id):
        """Get active property owners for a polygon"""
        return cls.objects.filter(
            polygon_id=polygon_id,
            is_active=True,
            deleted_at__isnull=True
        ).order_by('-created_at')
    
    @classmethod
    def get_by_session(cls, session_id):
        """Get property owners recorded in a session"""
        return cls.objects.filter(
            session_id=session_id,
            deleted_at__isnull=True
        ).order_by('-created_at')


#####################################################################################################

# ============================================================
# Pass Property / Skip Collection
# ============================================================

class PassProperty(models.Model):
    """
    Records when a property is passed or skipped during data collection.
    This could be due to various reasons like:
    - Property is inaccessible
    - No one available to provide information
    - Security concerns
    - Other operational reasons
    """
    
    # Reason choices
    class PassReason(models.TextChoices):
        INACCESSIBLE = 'inaccessible', 'Property Inaccessible'
        NO_ANSWER = 'no_answer', 'No Answer / No Response'
        SECURITY = 'security', 'Security Concerns'
        VACANT = 'vacant', 'Property Vacant'
        UNDER_CONSTRUCTION = 'under_construction', 'Under Construction'
        WRONG_ADDRESS = 'wrong_address', 'Wrong Address'
        REFUSED = 'refused', 'Owner/Resident Refused'
        NO_CONSENT = 'no_consent', 'No Consent to Collect Data'
        OTHER = 'other', 'Other Reason'
    
    # Reason for passing the property
    reason = models.CharField(
        max_length=50,
        choices=PassReason.choices,
        db_index=True,
        help_text="Reason why the property was passed"
    )
    
    # Additional notes/comments
    notes = models.TextField(
        blank=True, 
        null=True,
        help_text="Additional details about why the property was passed"
    )
    
    # Relationships
    polygon = models.ForeignKey(
        Polygon,
        on_delete=models.CASCADE,
        related_name='pass_records',
        db_column='polygon_id',
        help_text="The property that was passed"
    )
    
    agent = models.ForeignKey(
        UserModel,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='passed_properties',
        db_column='agent_id',
        help_text="The collector/agent who passed the property"
    )
    
    session = models.ForeignKey(
        Session,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pass_records',
        db_column='session_id',
        help_text="The collection session during which the property was passed"
    )
    
    # Status and tracking
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    passed_at = models.DateTimeField(auto_now_add=True, help_text="When the property was passed")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'pass_property'
        ordering = ['-passed_at']
        indexes = [
            models.Index(fields=['polygon']),
            models.Index(fields=['agent']),
            models.Index(fields=['reason']),
            models.Index(fields=['passed_at']),
            models.Index(fields=['session']),
        ]
        verbose_name = 'Passed Property'
        verbose_name_plural = 'Passed Properties'
    
    def __str__(self):
        polygon_info = f"Polygon {self.polygon_id}" if self.polygon else "Unknown Property"
        reason_display = self.get_reason_display()
        return f"{polygon_info} - {reason_display}"
    
    def save(self, *args, **kwargs):
        # Auto-clean notes
        if self.notes:
            self.notes = self.notes.strip()
        
        super().save(*args, **kwargs)
    
    @classmethod
    def get_by_polygon(cls, polygon_id):
        """Get all pass records for a specific polygon"""
        return cls.objects.filter(
            polygon_id=polygon_id,
            is_active=True,
            deleted_at__isnull=True
        ).order_by('-passed_at')
    
    @classmethod
    def get_by_agent(cls, agent_id):
        """Get all pass records by a specific agent"""
        return cls.objects.filter(
            agent_id=agent_id,
            is_active=True,
            deleted_at__isnull=True
        ).order_by('-passed_at')
    
    @classmethod
    def get_by_reason(cls, reason):
        """Get all pass records with a specific reason"""
        return cls.objects.filter(
            reason=reason,
            is_active=True,
            deleted_at__isnull=True
        ).order_by('-passed_at')


# ============================================================
# No Property Contact Available
# ============================================================

class NoPropertyContactAvailable(models.Model):
    """
    Records when no contact person is available at a property.
    This is different from passing a property - it specifically indicates
    that the property exists but no contact person is available to provide
    information.
    """
    
    # No contact reason choices
    class NoContactReason(models.TextChoices):
        NO_ONE_HOME = 'no_one_home', 'No One Home'
        UNAVAILABLE = 'unavailable', 'Contact Person Unavailable'
        WORKING_HOURS = 'working_hours', 'Away During Working Hours'
        TRAVELING = 'traveling', 'Traveling/Absent'
        BUSINESS_HOURS = 'business_hours', 'Business Closed'
        AFTER_HOURS = 'after_hours', 'After Business Hours'
        OTHER = 'other', 'Other Reason'
    
    # The user/collector who attempted contact
    user = models.ForeignKey(
        UserModel,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='no_contact_records',
        db_column='user_id',
        help_text="The collector who attempted to make contact"
    )
    
    # The property being assessed
    polygon = models.ForeignKey(
        Polygon,
        on_delete=models.CASCADE,
        related_name='no_contact_records',
        db_column='polygon_id',
        help_text="The property with no contact available"
    )
    
    # Flag to indicate no contact is available
    is_no_contact = models.BooleanField(
        default=True,
        help_text="Indicates that no contact is available at this property"
    )
    
    # Optional fields for additional context
    reason = models.CharField(
        max_length=50,
        choices=NoContactReason.choices,
        blank=True, 
        null=True,
        help_text="Specific reason why contact is not available"
    )
    
    notes = models.TextField(
        blank=True, 
        null=True,
        help_text="Additional notes about the contact attempt"
    )
    
    session = models.ForeignKey(
        Session,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='no_contact_records',
        db_column='session_id',
        help_text="The collection session during which contact was attempted"
    )
    
    # Contact attempt tracking
    attempt_count = models.IntegerField(
        default=1,
        help_text="Number of contact attempts made"
    )
    
    last_attempt_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Timestamp of the last contact attempt"
    )
    
    next_attempt_suggested = models.DateTimeField(
        null=True, blank=True,
        help_text="Suggested time for next contact attempt"
    )
    
    # Status and tracking
    is_active = models.BooleanField(default=True)
    resolved = models.BooleanField(
        default=False,
        help_text="Whether this no-contact issue has been resolved"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        UserModel,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resolved_no_contact',
        db_column='resolved_by',
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'no_property_contact_available'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['polygon']),
            models.Index(fields=['user']),
            models.Index(fields=['is_no_contact']),
            models.Index(fields=['created_at']),
            models.Index(fields=['resolved']),
            models.Index(fields=['session']),
        ]
        unique_together = [['polygon', 'is_no_contact']]  # Prevent duplicate active no-contact records for same polygon
        verbose_name = 'No Property Contact'
        verbose_name_plural = 'No Property Contacts'
    
    def __str__(self):
        polygon_info = f"Polygon {self.polygon_id}" if self.polygon else "Unknown Property"
        user_info = f"by {self.user.name}" if self.user else ""
        return f"{polygon_info} - No Contact Available {user_info}"
    
    def save(self, *args, **kwargs):
        # Set last_attempt_at if not set
        if not self.last_attempt_at:
            from django.utils import timezone
            self.last_attempt_at = timezone.now()
        
        # Auto-clean notes
        if self.notes:
            self.notes = self.notes.strip()
        
        super().save(*args, **kwargs)
    
    def resolve(self, resolver, notes=None):
        """
        Mark this no-contact record as resolved
        """
        from django.utils import timezone
        
        self.resolved = True
        self.resolved_at = timezone.now()
        self.resolved_by = resolver
        self.is_active = False
        
        if notes:
            self.notes = (self.notes or "") + f"\n\nResolved: {notes}"
        
        self.save()
    
    def increment_attempt(self, notes=None):
        """
        Increment the contact attempt count
        """
        from django.utils import timezone
        
        self.attempt_count += 1
        self.last_attempt_at = timezone.now()
        
        if notes:
            self.notes = (self.notes or "") + f"\n\nAttempt {self.attempt_count}: {notes}"
        
        self.save()
    
    @classmethod
    def get_active_by_polygon(cls, polygon_id):
        """Get active no-contact record for a specific polygon"""
        return cls.objects.filter(
            polygon_id=polygon_id,
            is_no_contact=True,
            is_active=True,
            resolved=False,
            deleted_at__isnull=True
        ).first()
    
    @classmethod
    def get_by_user(cls, user_id, resolved=False):
        """Get no-contact records for a specific collector"""
        queryset = cls.objects.filter(
            user_id=user_id,
            is_no_contact=True,
            deleted_at__isnull=True
        )
        
        if not resolved:
            queryset = queryset.filter(resolved=False)
        
        return queryset.order_by('-created_at')

# ============================================================
# Proxy / Alias models (no extra DB tables)
# ============================================================

class Bops(Business):
    """Backward-compatibility alias for Business."""
    class Meta:
        proxy = True
        verbose_name        = 'LANMA Business'
        verbose_name_plural = 'LANMA Businesses'


class BopsBills(Bill):
    """Backward-compatibility alias for Bill (BOP type)."""
    class Meta:
        proxy = True
        verbose_name        = 'Business Bill'
        verbose_name_plural = 'Business Bills'


class PropertyBill(Bill):
    """Proxy for Bills of type PR — no extra table."""
    class Meta:
        proxy = True
        verbose_name        = 'Property Bill'
        verbose_name_plural = 'Property Bills'


class BusinessBill(Bill):
    """Proxy for Bills of type BOP — no extra table."""
    class Meta:
        proxy = True
        verbose_name        = 'Business Bill'
        verbose_name_plural = 'Business Bills'

    @property
    def business(self):
        return None


# core/models.py - Update Staff proxy model

class Staff(UserModel):
    """Backward-compatibility alias for UserModel."""
    class Meta:
        proxy = True
        verbose_name = 'Staff'
        verbose_name_plural = 'Staff'
    
    @property
    def staff_id(self):
        return self.employee_id