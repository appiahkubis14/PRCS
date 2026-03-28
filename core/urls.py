from django.urls import path
from core.main import *
from django.contrib.auth import views as auth_views
from core.views.property_registry.property import *
from core.views.property_registry.properties import *
# from core.views.property_registry.classification import *
from core.views.property_registry.owner import *
from core.views.property_registry.map import *
from core.views.billing.bill_generation import *
# from core.views.billing.rate_management import *
# from core.views.billing.tax_calculation import *
# from core.views.billing.billing_cycles import *

from core.views.map.map import *
from core.views.payment_views import *
from core.views.billing.payment_monitoring import *
from core.views.billing.payment_track import *
from core.views.dashboard.dashboard_new import *
from core.views.users import *
from core.views.permit import *
from core.views.views_tiles import get_properties_points, pmtiles_options, properties_simple_geojson, property_geojson_for_highlight, serve_pmtiles


urlpatterns = [
    path('dashboard/', index, name='dashboard'),
    path('welcome/', dashboard_view, name='welcome'),
    path('', landing, name='landing'),
    path('login/', auth_views.LoginView.as_view(template_name="auth/auth-login.html"), name='login'),
    path('logout/', custom_logout, name='logout'),
    path('change-password/', change_password, name='change_password'),

    # path('property-registry/', property_registry, name='property-registry'),
    # path('api/properties/', get_properties, name='get-properties'),
    # path('api/properties/add/', add_property, name='add-property'),
    # path('api/properties/<int:property_id>/', get_property_detail, name='get-property-detail'),
    # path('api/properties/<int:property_id>/update/', update_property, name='update-property'),
    # path('api/properties/<int:property_id>/delete/', delete_property, name='delete-property'),

    # path('property-valuation/', property_valuation, name='property-valuation'),
    # path('api/valuations/', get_valuations, name='get-valuations'),
    # path('api/valuations/add/', create_valuation, name='create-valuation'),
    # path('api/valuations/<int:bill_id>/', get_valuation_detail, name='get-valuation-detail'),
    # path('api/valuations/<int:bill_id>/update/', update_valuation, name='update-valuation'),
    # path('api/valuations/<int:bill_id>/delete/', delete_valuation, name='delete-valuation'),
#     path('api/properties/<int:property_id>/details/', get_property_details, name='get-property-details'),

    # path('property-classification/', property_classification, name='property-classification'),
    # path('api/classifications/', get_classifications, name='get-classifications'),
    # path('api/classifications/<int:property_id>/update/', update_classification, name='update-classification'),
    # path('api/classifications/<int:property_id>/analysis/', get_classification_analysis, name='get-classification-analysis'),
    # path('api/classifications/stats/', get_classification_stats, name='get-classification-stats'),

    # Owner Management URLs
    path('owners/', owner_management, name='owner_management'),
    path('api/owners/', get_owners, name='get_owners'),
    path('api/owners/<int:owner_id>/', get_owner_detail, name='get_owner_detail'),
    path('api/owners/<int:owner_id>/update/', update_owner, name='update_owner'),
    path('api/owners/stats/', get_owner_stats, name='get_owner_stats'),
    path('api/owners/search/', search_owners, name='search_owners'),
    path('api/owners/export/', export_owners, name='export_owners'),
    path('api/properties/<int:property_id>/owners/', get_property_owners, name='get_property_owners'),



    path('bill-generation/', bill_generation_page, name='bill_generation'),
    path('api/bills/', view_bill, name='get_bills'),
    path('api/bills/generate/', generate_bill, name='generate_bill'),
    path('api/bills/bulk-generate/', bulk_generate_bills, name='bulk_generate_bills'),
    path('api/bills/<int:bill_id>/', get_bill_details, name='get_bill_details'),
    path('api/bills/<int:bill_id>/update/', update_bill, name='update_bill'),
    path('api/bills/<int:bill_id>/delete/', delete_bill, name='delete_bill'),
    path('api/properties/billing/', get_properties_for_billing, name='get_properties_for_billing'),
    path('api/billing-cycles/', get_billing_cycles, name='get_billing_cycles'),
    path('api/calculate-tax/', calculate_tax_amount, name='calculate_tax'),

    path('api/bops/list/', get_bops_list, name='get_bops_list'),
    path('api/bops-bills/years/', get_billing_years, name='get_billing_years'),
    path('api/bops-bills/blocks/', get_bops_blocks, name='get_bops_blocks'),
    path('api/bops-bills/blocks-by-division/', get_bops_blocks_by_division, name='get_bops_blocks_by_division'),
    path('api/bops-bills/divisions/', get_bops_divisions, name='get_bops_divisions'),
    path('api/bops-bills/generate/', generate_bops_bills, name='generate_bops_bills'),        # ← updated view
    path('api/bops-bills/list/', get_bops_bills_list, name='get_bops_bills_list'),
    path('api/bops-bills/<int:bill_id>/regenerate/', regenerate_bops_bill, name='regenerate_bops_bill'),
    path('api/bops-bills/<int:bill_id>/send-message/', send_bops_bill_message, name='send_bops_bill_message'),
    path('api/bops-bills/<int:bill_id>/sms/resend/', resend_bill_sms, name='resend_bill_sms'),  # ← new
    path('bops-bills/', bops_bills_list_page, name='bops_bills_list'),
    path('bops-bills/<int:bill_id>/bill/', bops_bill_receipt, name='bops_bill_receipt'),

    path('bopeasycollectible/', bop_easy_collectible_list, name='bopeasycollectible'),

    # path('billing/rates-management/', rate_management_page, name='rate_management'),
    # path('api/tax-rates/', get_tax_rates, name='get_tax_rates'),
    # path('api/tax-rates/create/', create_tax_rate, name='create_tax_rate'),
    # path('api/tax-rates/<int:rate_id>/update/', update_tax_rate, name='update_tax_rate'),
    # path('api/tax-rates/<int:rate_id>/delete/', delete_tax_rate, name='delete_tax_rate'),
    # path('api/zones-property-types/', get_zones_and_property_types, name='get_zones_property_types'),
    # path('api/tax-rates/history/<int:zone_id>/<int:property_type_id>/', get_tax_rate_history, name='get_tax_rate_history'),
    # path('api/tax-rates/current-report/', get_current_rates_report, name='get_current_rates_report'),
    # path('api/tax-rates/bulk-update/', bulk_update_rates, name='bulk_update_rates'),

    # path('billing/tax-calculation/', tax_calculation_page, name='tax_calculation'),
    # path('api/tax/calculate/', calculate_tax_for_property, name='calculate_tax'),
    # path('api/tax/bulk-calculate/', bulk_tax_calculation, name='bulk_tax_calculation'),
    # path('api/tax/recent-calculations/', get_recent_calculations, name='recent_calculations'),
    # path('api/tax/history/<int:property_id>/', get_tax_calculation_history, name='get_tax_history'),
    # path('api/tax/simulate/', simulate_tax_scenario, name='simulate_tax_scenario'),
    # path('api/tax/summary-report/', get_tax_summary_report, name='get_tax_summary'),
    # path('api/tax/save-draft/', save_calculation_as_draft, name='save_calculation_draft'),

    # path('billing-cycles/', billing_cycles_page, name='billing_cycles'),
    # path('api/billing-cycles/', get_billing_cycles_list, name='get_billing_cycles_list'),
    # path('api/billing-cycles/create/', create_billing_cycle, name='create_billing_cycle'),
    # path('api/billing-cycles/<int:cycle_id>/update/', update_billing_cycle, name='update_billing_cycle'),
    # path('api/billing-cycles/<int:cycle_id>/delete/', delete_billing_cycle, name='delete_billing_cycle'),
    # path('api/billing-cycles/<int:cycle_id>/', get_billing_cycle_details, name='get_billing_cycle_details'),
    # path('api/billing-cycles/upcoming/', get_upcoming_cycles, name='get_upcoming_cycles'),
    # path('api/billing-cycles/generate-batch/', generate_cycles_batch, name='generate_cycles_batch'),
    # path('api/billing-cycles/performance/', get_cycle_performance, name='get_cycle_performance'),

    path('properties/mapping/', property_mapping, name='property_mapping'),
    path('api/properties/geojson/', get_properties_geojson, name='get_properties_geojson'),
    path('api/zones/geojson/', get_zones_geojson, name='get_zones_geojson'),
    path('api/districts/geojson/', get_districts_geojson, name='get_districts_geojson'),
    path('api/bops/geojson/', get_bops_geojson, name='get_bops_geojson'),
    path('api/property/<str:property_id>/', get_property_details, name='get_property_details'),
    path('api/search/properties/', search_properties, name='search_properties'),

    path('api/map/properties/', properties_list, name='properties_list'),
    path('api/map/properties/<str:identifier>/', property_detail, name='property_detail'),
    path('api/map/zones/', zones_list, name='zones_list'),
    path('api/map/zones/performance/', zones_performance, name='zones_performance'),
    path('api/map/districts/', districts_list, name='districts_list'),
    path('api/map/search/', search_properties, name='search_properties'),
    path('api/map/heatmap/', heatmap_data, name='heatmap_data'),

    # ── Payment integration (Kowri) ────────────────────────────────────────
    path('api/payments/kowri/lookup/', kowri_bill_lookup, name='kowri_bill_lookup'),
    path('api/payments/kowri/notification/', kowri_payment_notification, name='kowri_payment_notification'),
    path('api/payments/status/<str:bill_type>/<int:bill_id>/', get_payment_status, name='get_payment_status'),
    path('api/payments/transactions/', list_payment_transactions, name='list_payment_transactions'),
    path('api/payments/transactions/<str:transaction_id>/', get_transaction_detail, name='transaction_detail'),
    path('api/payments/providers/', get_payment_providers, name='payment_providers'),
    path('api/payments/notifications/<int:notification_id>/retry/', retry_failed_notification, name='retry_notification'),

    # ── Payment link click tracking ────────────────────────────────────────
    path('api/payments/track-click/', track_payment_link_click, name='track_payment_click'),
    path('pay/l/<str:bill_type>/<str:bill_number>/', payment_link_redirect, name='payment_link_redirect'),
    path('pay/l/<str:bill_type>/<str:bill_number>/<str:link_type>/', payment_link_redirect, name='payment_link_redirect_type'),

    # ── Payment monitoring ─────────────────────────────────────────────────
    path('payments/monitoring/', payment_monitoring_dashboard, name='payment_monitoring'),
    path('api/payments/bops-bills/tracking/', get_bops_bills_with_tracking, name='bops_bills_tracking'),
    path('api/payments/bops-bills/<int:bill_id>/detail/', get_bops_bill_detail, name='bops_bill_detail'),
    path('api/payments/dashboard/stats/', get_dashboard_stats, name='dashboard_stats'),

    # ── Revenue dashboard ──────────────────────────────────────────────────
    # path('revenue-dashboard/', revenue_dashboard, name='revenue_dashboard'),
    # path('api/dashboard/stats/', get_dashboard_stats, name='dashboard_stats'),
    # path('api/dashboard/revenue-trends/', get_revenue_trends, name='revenue_trends'),
    # path('api/dashboard/top-performers/', get_top_performers, name='top_performers'),

#     # ── Map tiles ──────────────────────────────────────────────────────────
    path('tiles/<str:filename>', serve_pmtiles, name='serve_pmtiles'),
    path('tiles/<str:filename>', pmtiles_options, name='pmtiles-options'),
    path('api/properties/points/', get_properties_points, name='properties-points'),
    path('api/properties/geojson/simple/', properties_simple_geojson, name='properties-simple-geojson'),
    path('api/properties/<int:property_id>/geojson/', property_geojson_for_highlight, name='property-geojson'),


    # Main page
    path('bops/properties/', bops_properties_page, name='bops_properties_page'),
    
    # API endpoints
    path('api/bops/properties/list/', list_bops_properties, name='list_bops_properties'),
    path('api/bops/properties/create/', create_bops_property, name='create_bops_property'),
    path('api/bops/properties/<int:property_id>/', get_bops_property, name='get_bops_property'),
    path('api/bops/properties/<int:property_id>/update/', update_bops_property, name='update_bops_property'),
    path('api/bops/properties/<int:property_id>/delete/', delete_bops_property, name='delete_bops_property'),
    path('api/bops/properties/bulk-delete/', bulk_delete_bops_properties, name='bulk_delete_bops_properties'),
    path('api/bops/properties/export/', export_bops_properties, name='export_bops_properties'),

    # Main page
    path('properties/', properties_page, name='properties_page'),
    
    # API endpoints
    path('api/properties/list/', list_properties, name='list_properties'),
    path('api/properties/create/', create_property, name='create_property'),
    path('api/properties/<int:property_id>/', get_property, name='get_property'),
    path('api/properties/<int:property_id>/update/', update_property, name='update_property'),
    path('api/properties/<int:property_id>/delete/', delete_property, name='delete_property'),
    path('api/properties/bulk-delete/', bulk_delete_properties, name='bulk_delete_properties'),
    path('api/properties/export/', export_properties, name='export_properties'),
    
#     # Options endpoints
#     path('api/zones/options/', get_zone_options, name='get_zone_options'),
#     path('api/property-types/options/', get_property_type_options, name='get_property_type_options'),


#     # API endpoints for dashboard data
#     path('api/dashboard/performance-stats/', 
#          dashboard_performance_stats, 
#          name='dashboard_performance_stats'),
    
#     path('api/dashboard/growth-trend/', 
#          dashboard_growth_trend, 
#          name='dashboard_growth_trend'),
    
#     path('api/dashboard/category-distribution/', 
#          dashboard_category_distribution, 
#          name='dashboard_category_distribution'),
    
#     path('api/dashboard/district-performance/', 
#          dashboard_district_performance, 
#          name='dashboard_district_performance'),
    
#     path('api/dashboard/recent-activity/', 
#          dashboard_recent_activity, 
#          name='dashboard_recent_activity'),
    
#     path('api/dashboard/payment-patterns/', 
#          dashboard_payment_patterns, 
#          name='dashboard_payment_patterns'),
    
#     path('api/dashboard/quick-stats/', 
#          dashboard_quick_stats, 
#          name='dashboard_quick_stats'),
    
#     path('api/dashboard/export/', 
#          dashboard_export_data, 
#          name='dashboard_export'),

#     path('field-dashboard/', 
#          field_collection_dashboard, 
#          name='field_collection_dashboard'),
    
#     path('api/field-dashboard/stats/', 
#          field_dashboard_stats, 
#          name='field_dashboard_stats'),
    
#     path('api/field-dashboard/collection-trend/', 
#          field_dashboard_collection_trend, 
#          name='field_dashboard_collection_trend'),
    
#     path('api/field-dashboard/activities/', 
#          field_dashboard_activities, 
#          name='field_dashboard_activities'),
    
#     path('api/field-dashboard/projections/', 
#          field_dashboard_projections, 
#          name='field_dashboard_projections'),
    
#     path('api/field-dashboard/snapshots/', 
#          field_dashboard_snapshots, 
#          name='field_dashboard_snapshots'),



    # User Management URLs
    path('users/', user_management, name='user_management'),
    path('api/users/', get_users, name='get_users'),
    path('api/users/create/', create_user, name='create_user'),
    path('api/users/<int:user_id>/', get_user_detail, name='get_user_detail'),
    path('api/users/<int:user_id>/update/', update_user, name='update_user'),
    path('api/users/<int:user_id>/delete/', delete_user, name='delete_user'),
    path('api/users/<int:user_id>/reset-password/', reset_user_password, name='reset_user_password'),
    path('api/users/bulk-delete/', bulk_delete_users, name='bulk_delete_users'),
    path('api/users/stats/', get_user_stats, name='get_user_stats'),
    path('api/users/supervisors/', get_supervisors, name='get_supervisors'),




# Field Collection Dashboard
    path('revenue-dashboard/', field_collection_dashboard, name='field_collection_dashboard'),
    
    # API Endpoints
    path('api/field-stats/', field_dashboard_stats, name='field_stats'),
    path('api/field-trend/', field_dashboard_collection_trend, name='field_trend'),
    path('api/field-activities/', field_dashboard_activities, name='field_activities'),
    path('api/field-snapshots/', field_dashboard_snapshots, name='field_snapshots'),
    # Permit Management URLs
    path('permits/', permit_management, name='permit_management'),
    path('api/permits/', get_permits, name='get_permits'),
    path('api/permits/<int:permit_id>/', get_permit_detail, name='get_permit_detail'),
    path('api/permits/<int:permit_id>/approve/', approve_permit, name='approve_permit'),
    path('api/permits/<int:permit_id>/reject/', reject_permit, name='reject_permit'),
    path('api/permits/<int:permit_id>/delete/', delete_permit, name='delete_permit'),
    path('api/permits/bulk-approve/', bulk_approve_permits, name='bulk_approve_permits'),
    path('api/permits/stats/', get_permit_stats, name='get_permit_stats'),
    path('api/permits/export/', export_permits, name='export_permits'),

]