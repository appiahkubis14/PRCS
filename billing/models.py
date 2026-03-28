# from django.db import models
# from core.models import TimeStampModel


# class BopEasyCollectible(TimeStampModel):
#     """
#     Model for BOP Easy Collectibles with account, business, and financial information
#     """
#     account_no = models.CharField(max_length=100, unique=True, verbose_name="Account Number")
#     business_name = models.CharField(max_length=255, verbose_name="Business Name")
#     owner_name = models.CharField(max_length=255, verbose_name="Owner Name")
#     business_location = models.CharField(max_length=500, verbose_name="Business Location")
#     rev_cat = models.CharField(max_length=500, verbose_name="Revenue Category")
#     rev_item = models.CharField(max_length=500, verbose_name="Revenue Item")
#     arrears = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Arrears")
#     yearly_fee = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Yearly Fee")
#     amt_due = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Amount Due")
    
#     class Meta:
#         db_table = 'billing_bop_easy_collectible'
#         verbose_name = "BOP Easy Collectible"
#         verbose_name_plural = "BOP Easy Collectibles"
#         ordering = ['-created_at']
    
#     def __str__(self):
#         return f"{self.account_no} - {self.business_name}"


# class PropertyGated(TimeStampModel):
#     """
#     Model for gated properties/communities
#     """
#     property_code = models.CharField(max_length=100, unique=True, verbose_name="Property Code")
#     property_name = models.CharField(max_length=255, verbose_name="Property Name")
#     location = models.CharField(max_length=500, verbose_name="Location")
#     gate_name = models.CharField(max_length=255, blank=True, verbose_name="Gate Name")
#     property_type = models.CharField(max_length=100, blank=True, verbose_name="Property Type")
#     description = models.TextField(blank=True, verbose_name="Description")
#     is_active = models.BooleanField(default=True, verbose_name="Is Active")
    
#     class Meta:
#         verbose_name = "Property - Gated"
#         verbose_name_plural = "Properties - Gated"
#         ordering = ['-created_at']
    
#     def __str__(self):
#         return f"{self.property_code} - {self.property_name}"


# class PropertyResidential(TimeStampModel):
#     """
#     Model for residential properties
#     """
#     property_code = models.CharField(max_length=100, unique=True, verbose_name="Property Code")
#     property_name = models.CharField(max_length=255, verbose_name="Property Name")
#     location = models.CharField(max_length=500, verbose_name="Location")
#     address = models.TextField(blank=True, verbose_name="Address")
#     property_type = models.CharField(max_length=100, blank=True, verbose_name="Property Type")
#     description = models.TextField(blank=True, verbose_name="Description")
#     is_active = models.BooleanField(default=True, verbose_name="Is Active")
    
#     class Meta:
#         verbose_name = "Property - Residential"
#         verbose_name_plural = "Properties - Residential"
#         ordering = ['-created_at']
    
#     def __str__(self):
#         return f"{self.property_code} - {self.property_name}"


# class BopMelchia(TimeStampModel):
#     """
#     Model for BOP MELCHIA
#     """
#     code = models.CharField(max_length=100, unique=True, verbose_name="Code")
#     name = models.CharField(max_length=255, verbose_name="Name")
#     location = models.CharField(max_length=500, blank=True, verbose_name="Location")
#     description = models.TextField(blank=True, verbose_name="Description")
#     is_active = models.BooleanField(default=True, verbose_name="Is Active")
    
#     class Meta:
#         verbose_name = "BOP MELCHIA"
#         verbose_name_plural = "BOP MELCHIA"
#         ordering = ['-created_at']
    
#     def __str__(self):
#         return f"{self.code} - {self.name}"
