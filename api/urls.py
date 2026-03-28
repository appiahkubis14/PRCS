# ============================================================
# api/urls.py - Complete rewrite to match documentation
# ============================================================

from django.urls import path
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

from .views import *
from .views_v2 import *

schema_view = get_schema_view(
    openapi.Info(
        title="GEMA Mobile App API",
        default_version='v1',
        description="API for GEMA Mobile App - Property and Business Data Collection",
        contact=openapi.Contact(email="support@gema.gov.gh"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)
urlpatterns = [
    # Auth endpoints
    path('v1/auth/request-otp', RequestOTPView.as_view(), name='request-otp'),
    path('v1/auth/verify-otp', VerifyOTPView.as_view(), name='verify-otp'),
    path('v1/auth/login', LoginView.as_view(), name='api-login1'),  # Keep for backward compat
    path('v1/auth/refresh', RefreshTokenView.as_view(), name='refresh'),
    path('v1/auth/logout', LogoutView.as_view(), name='logout'),
    path('v1/auth/change-password', ChangePasswordView.as_view(), name='change-password'),
    
    # Sync endpoints
    path('v1/sync/assignments/<str:collectorId>', FetchAssignmentsView.as_view(), name='assignments'),
    path('v1/sync/batch', SyncBatchView.as_view(), name='sync-batch'),
    path('v1/sync/notifications', FetchNotificationsView.as_view(), name='notifications'),
    path('v1/sync/rejected-entries', RejectedEntriesView.as_view(), name='rejected-entries'),  # Added
    
    # Polygon endpoints
    path('v1/polygons/<str:id>', SinglePolygonView.as_view(), name='polygon-detail'),
    
    # Settings endpoints
    path('v1/settings/lookups', LookupsView.as_view(), name='lookups'),
    path('v1/settings/form-lookups', FormLookupsView.as_view(), name='form-lookups'),
    path('v1/settings/business-types', BusinessTypesView.as_view(), name='business-types'),
    path('v1/settings/system', SystemSettingsView.as_view(), name='system-settings'),  # Added
    
    # Health endpoint
    path('v1/health', HealthView.as_view(), name='health'),

    # Swagger documentation (optional)
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),






    # Version check
    path('v2/version-check/', VersionCheckAPIView.as_view(), name='version-check'),
    
    # Authentication
    path('v2/login/', LoginAPIView.as_view(), name='api-login2'),
    
    # Property Owner endpoints
    path('v2/property-owner/', PropertyOwnerAPIView.as_view(), name='property-owner-list'),
    path('v2/property-owner/<int:entry_id>/', PropertyOwnerAPIView.as_view(), name='property-owner-detail'),
    
    # Property POC endpoints
    path('v2/property-poc/', PropertyPOCAPIView.as_view(), name='property-poc-list'),
    path('v2/property-poc/<int:entry_id>/', PropertyPOCAPIView.as_view(), name='property-poc-detail'),
    
    # Pass Property endpoints
    path('v2/pass-property/', PassPropertyAPIView.as_view(), name='pass-property'),
    path('v2/pass-property/<int:record_id>/', PassPropertyAPIView.as_view(), name='pass-property-detail'),
    
    # No Property Contact Available endpoints
    path('v2/no-contact/', NoPropertyContactAvailableAPIView.as_view(), name='no-contact'),
    path('v2/no-contact/<int:record_id>/', NoPropertyContactAvailableAPIView.as_view(), name='no-contact-detail'),
    path('v2/no-contact/<int:record_id>/increment/', NoPropertyContactAvailableAPIView.as_view(), name='no-contact-increment'),
    path('v2/no-contact/<int:record_id>/resolve/', NoPropertyContactAvailableAPIView.as_view(), name='no-contact-resolve'),
]