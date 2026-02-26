from enum import Enum

class Sidebar:
    sidebar_items = {
        "Dashboard Overview": {
            "icon": "fas fa-chart-pie",
            "sub_items": {
                "Revenue Dashboard": {
                    "icon": "fas fa-tachometer-alt", 
                    "url": "/revenue-dashboard/", 
                    "groups": ["Admin", "CEO", "Director", "Management", "Finance Team"]
                },
                # "Collection Performance": {
                #     "icon": "fas fa-money-bill-wave", 
                #     "url": "/dashboard/collection-performance/", 
                #     "groups": ["Admin", "CEO", "Director", "Finance Team", "Management"]
                # },
                # "Property Analytics": {
                #     "icon": "fas fa-chart-line", 
                #     "url": "/dashboard/property-analytics/", 
                #     "groups": ["Admin", "CEO", "Director", "Planning Team", "Finance Team"]
                # },
                # "Compliance Monitoring": {
                #     "icon": "fas fa-shield-alt", 
                #     "url": "/dashboard/compliance/", 
                #     "groups": ["Admin", "CEO", "Director", "Legal Team", "Finance Team"]
                # },
            },
        },
        
        # "Property Management": {
        #     "icon": "fas fa-home",
        #     "sub_items": {
        #         "Property Registry": {
        #             "icon": "fas fa-building", 
        #             "url": "/property-registry/", 
        #             "groups": ["Admin", "Assessment Team", "Planning Team", "GIS Team"]
        #         },
        #         "Property Valuation": {
        #             "icon": "fas fa-calculator", 
        #             "url": "/property-valuation/",
        #             "groups": ["Admin", "Assessment Team", "Finance Team", "Management"]
        #         },
        #         "Property Classification": {
        #             "icon": "fas fa-tags", 
        #             "url": "/property-classification/",
        #             "groups": ["Admin", "Assessment Team", "Planning Team", "Finance Team"]
        #         },
        #         "Owner Management": {
        #             "icon": "fas fa-users", 
        #             "url": "/property-owners/",
        #             "groups": ["Admin", "Assessment Team", "Customer Service", "Finance Team"]
        #         },
        #         "GIS Property Mapping": {
        #             "icon": "fas fa-map-marked-alt", 
        #             "url": "/properties/mapping/",
        #             "groups": ["Admin", "GIS Team", "Planning Team", "Assessment Team"]
        #         },
        #         # "Property Reports": {
        #         #     "icon": "fas fa-file-alt", 
        #         #     "groups": ["Admin", "CEO", "Director", "Management", "Finance Team"],
        #         #     "sub_items": {
        #         #         "Valuation Reports": {
        #         #             "icon": "fas fa-chart-pie", 
        #         #             "url": "/properties/reports/valuation/",
        #         #             "groups": ["Admin", "CEO", "Director", "Finance Team"]
        #         #         },
        #         #         "Property Inventory": {
        #         #             "icon": "fas fa-clipboard-list", 
        #         #             "url": "/properties/reports/inventory/",
        #         #             "groups": ["Admin", "Assessment Team", "Planning Team"]
        #         #         },
        #         #         "Ownership Trends": {
        #         #             "icon": "fas fa-chart-line", 
        #         #             "url": "/properties/reports/trends/",
        #         #             "groups": ["Admin", "CEO", "Director", "Planning Team"]
        #         #         },
        #         #     }
        #         # },
        #     }
        # },

        "Billing & Invoicing": {
            "icon": "fas fa-file-invoice-dollar",
            "sub_items": {
                "Bill Generation": {
                    "icon": "fas fa-receipt", 
                    "url": "/bill-generation/",
                    "groups": ["Admin", "Finance Team", "Billing Team"]
                },
                # "Rate Management": {
                #     "icon": "fas fa-percentage", 
                #     "url": "/billing/rates-management/",
                #     "groups": ["Admin", "Finance Team", "Management"]
                # },
                "Payment Monitoring": {
                    "icon": "fas fa-hand-holding-usd", 
                    "url": "/payments/monitoring/",
                    "groups": ["Admin", "Finance Team", "Assessment Team"]
                },
                # "Billing Cycles": {
                #     "icon": "fas fa-calendar-alt", 
                #     "url": "/billing-cycles/",
                #     "groups": ["Admin", "Finance Team", "Billing Team"]
                # },
                "BOP Bills": {
                    "icon": "fas fa-file-invoice", 
                    "url": "/bops-bills/",
                    "groups": ["Admin", "Finance Team", "Billing Team"]
                },
                # "Billing Reports": {
                #     "icon": "fas fa-file-contract", 
                #     "groups": ["Admin", "CEO", "Director", "Finance Team"],
                #     "sub_items": {
                #         "Billing Summary": {
                #             "icon": "fas fa-file-invoice", 
                #             "url": "/billing/reports/summary/",
                #             "groups": ["Admin", "Finance Team", "Management"]
                #         },
                #         "Revenue Projections": {
                #             "icon": "fas fa-chart-line", 
                #             "url": "/billing/reports/projections/",
                #             "groups": ["Admin", "CEO", "Director", "Finance Team"]
                #         },
                #     }
                # },
            }
        },
        
        # "Payment Processing": {
        #     "icon": "fas fa-credit-card",
        #     "sub_items": {
        #         "Payment Collection": {
        #             "icon": "fas fa-cash-register", 
        #             "url": "/payments/collection/",
        #             "groups": ["Admin", "Finance Team", "Cashiers", "Customer Service"]
        #         },
        #         "Mobile Payments": {
        #             "icon": "fas fa-mobile-alt", 
        #             "url": "/payments/mobile/",
        #             "groups": ["Admin", "Finance Team", "IT Team", "Customer Service"]
        #         },
        #         "Bank Transfers": {
        #             "icon": "fas fa-university", 
        #             "url": "/payments/bank/",
        #             "groups": ["Admin", "Finance Team", "Cashiers"]
        #         },
        #         "Payment Reconciliation": {
        #             "icon": "fas fa-balance-scale", 
        #             "url": "/payments/reconciliation/",
        #             "groups": ["Admin", "Finance Team", "Audit Team"]
        #         },
        #         "Payment Reports": {
        #             "icon": "fas fa-chart-bar", 
        #             "groups": ["Admin", "CEO", "Director", "Finance Team"],
        #             "sub_items": {
        #                 "Collection Performance": {
        #                     "icon": "fas fa-chart-line", 
        #                     "url": "/payments/reports/performance/",
        #                     "groups": ["Admin", "Finance Team", "Management"]
        #                 },
        #                 "Payment Channels": {
        #                     "icon": "fas fa-road", 
        #                     "url": "/payments/reports/channels/",
        #                     "groups": ["Admin", "Finance Team", "IT Team"]
        #                 },
        #             }
        #         },
        #     }
        # },




        
        # "Compliance & Enforcement": {
        #     "icon": "fas fa-gavel",
        #     "sub_items": {
        #         "Compliance Monitoring": {
        #             "icon": "fas fa-eye", 
        #             "url": "/compliance/monitoring/",
        #             "groups": ["Admin", "Legal Team", "Enforcement Team", "Finance Team"]
        #         },
        #         "Delinquency Management": {
        #             "icon": "fas fa-exclamation-triangle", 
        #             "url": "/compliance/delinquency/",
        #             "groups": ["Admin", "Legal Team", "Enforcement Team", "Finance Team"]
        #         },
        #         "Legal Actions": {
        #             "icon": "fas fa-balance-scale", 
        #             "url": "/compliance/legal-actions/",
        #             "groups": ["Admin", "Legal Team", "Director"]
        #         },
        #         "Penalty Management": {
        #             "icon": "fas fa-money-bill-wave", 
        #             "url": "/compliance/penalties/",
        #             "groups": ["Admin", "Legal Team", "Finance Team", "Enforcement Team"]
        #         },
        #         "Compliance Reports": {
        #             "icon": "fas fa-file-alt", 
        #             "url": "/compliance/reports/",
        #             "groups": ["Admin", "CEO", "Director", "Legal Team", "Management"]
        #         },
        #     }
        # },


        
        # "Customer Management": {
        #     "icon": "fas fa-users",
        #     "sub_items": {
        #         "Customer Portal": {
        #             "icon": "fas fa-user-circle", 
        #             "url": "/customers/portal/",
        #             "groups": ["Admin", "Customer Service", "Finance Team"]
        #         },
        #         "Account Management": {
        #             "icon": "fas fa-address-book", 
        #             "url": "/customers/accounts/",
        #             "groups": ["Admin", "Customer Service", "Finance Team"]
        #         },
        #         "Communication Center": {
        #             "icon": "fas fa-comments", 
        #             "url": "/customers/communication/",
        #             "groups": ["Admin", "Customer Service", "Finance Team"]
        #         },
        #         "Service Requests": {
        #             "icon": "fas fa-headset", 
        #             "url": "/customers/requests/",
        #             "groups": ["Admin", "Customer Service", "Assessment Team"]
        #         },
        #         "Customer Analytics": {
        #             "icon": "fas fa-chart-bar", 
        #             "url": "/customers/analytics/",
        #             "groups": ["Admin", "Management", "Finance Team", "Customer Service"]
        #         },
        #     }
        # },

        # "Financial Management": {
        #     "icon": "fas fa-chart-line",
        #     "sub_items": {
        #         "Revenue Tracking": {
        #             "icon": "fas fa-money-check", 
        #             "url": "/financial/revenue/",
        #             "groups": ["Admin", "Finance Team", "Management", "Director"]
        #         },
        #         "Expense Management": {
        #             "icon": "fas fa-receipt", 
        #             "url": "/financial/expenses/",
        #             "groups": ["Admin", "Finance Team", "Management"]
        #         },
        #         "Budget Planning": {
        #             "icon": "fas fa-chart-pie", 
        #             "url": "/financial/budget/",
        #             "groups": ["Admin", "Finance Team", "CEO", "Director", "Management"]
        #         },
        #         "Financial Reports": {
        #             "icon": "fas fa-file-invoice-dollar", 
        #             "url": "/financial/reports/",
        #             "groups": ["Admin", "Finance Team", "CEO", "Director", "Audit Team"]
        #         },
        #         "Audit Trail": {
        #             "icon": "fas fa-search-dollar", 
        #             "url": "/financial/audit/",
        #             "groups": ["Admin", "Finance Team", "Audit Team", "Director"]
        #         },
        #     }
        # },
        
        "GIS & Spatial Analysis": {
            "icon": "fas fa-map",
            "sub_items": {
                "Property Mapping": {
                    "icon": "fas fa-map-marked-alt", 
                    "url": "/properties/mapping/",
                    "groups": ["Admin", "GIS Team", "Planning Team", "Assessment Team"]
                },
                # "Revenue Heat Maps": {
                #     "icon": "fas fa-fire", 
                #     "url": "/gis/heatmaps/",
                #     "groups": ["Admin", "GIS Team", "Planning Team", "Management"]
                # },
                # "Zone Management": {
                #     "icon": "fas fa-layer-group", 
                #     "url": "/gis/zones/",
                #     "groups": ["Admin", "GIS Team", "Planning Team", "Assessment Team"]
                # },
                # "Spatial Analytics": {
                #     "icon": "fas fa-chart-area", 
                #     "url": "/gis/analytics/",
                #     "groups": ["Admin", "GIS Team", "Planning Team", "Finance Team"]
                # },
                # "Measurement Tools": {
                #     "icon": "fas fa-ruler-combined", 
                #     "url": "/gis/measurement/",
                #     "groups": ["Admin", "GIS Team", "Assessment Team", "Planning Team"]
                # },
            }
        },
        
        # "Reports & Analytics": {
        #     "icon": "fas fa-chart-bar",
        #     "sub_items": {
        #         "Revenue Analytics": {
        #             "icon": "fas fa-chart-line", 
        #             "url": "/analytics/revenue/",
        #             "groups": ["Admin", "CEO", "Director", "Finance Team", "Management"]
        #         },
        #         "Collection Analytics": {
        #             "icon": "fas fa-money-bill", 
        #             "url": "/analytics/collection/",
        #             "groups": ["Admin", "CEO", "Director", "Finance Team"]
        #         },
        #         "Compliance Analytics": {
        #             "icon": "fas fa-shield-alt", 
        #             "url": "/analytics/compliance/",
        #             "groups": ["Admin", "CEO", "Director", "Legal Team"]
        #         },
        #         "Performance Metrics": {
        #             "icon": "fas fa-tachometer-alt", 
        #             "url": "/analytics/performance/",
        #             "groups": ["Admin", "CEO", "Director", "Management"]
        #         },
        #         "Automated Reports": {
        #             "icon": "fas fa-file-export", 
        #             "url": "/analytics/automated-reports/",
        #             "groups": ["Admin", "CEO", "Director", "Management"]
        #         },
        #     }
        # },
        
        # "User Management": {
        #     "icon": "fas fa-users-cog",
        #     "sub_items": {
        #         "User Accounts": {
        #             "icon": "fas fa-user-friends", 
        #             "url": "/users/accounts/", 
        #             "groups": ["Admin", "Director", "HR Team"]
        #         },
        #         "Role Management": {
        #             "icon": "fas fa-user-tag", 
        #             "url": "/users/roles/", 
        #             "groups": ["Admin", "HR Team"]
        #         },
        #         # "Department Management": {
        #         #     "icon": "fas fa-sitemap", 
        #         #     "url": "/users/departments/", 
        #         #     "groups": ["Admin", "Director", "HR Team"]
        #         # },
        #         "Access Logs": {
        #             "icon": "fas fa-history", 
        #             "url": "/users/access-logs/", 
        #             "groups": ["Admin", "IT Team"]
        #         },
        #     },
        # },
        
        # "System Administration": {
        #     "icon": "fas fa-cogs",
        #     "sub_items": {
        #         "System Configuration": {
        #             "icon": "fas fa-sliders-h", 
        #             "url": "/admin/system/", 
        #             "groups": ["Admin", "IT Team"]
        #         },
        #         "Notification Settings": {
        #             "icon": "fas fa-bell", 
        #             "url": "/admin/notifications/", 
        #             "groups": ["Admin", "Director", "IT Team"]
        #         },
        #         "Data Management": {
        #             "icon": "fas fa-database", 
        #             "url": "/admin/data/", 
        #             "groups": ["Admin", "IT Team"]
        #         },
        #         "Backup & Recovery": {
        #             "icon": "fas fa-hdd", 
        #             "url": "/admin/backup/", 
        #             "groups": ["Admin", "IT Team"]
        #         },
        #     },
        # },
        
        # "Admin Panel": {
        #     "icon": "fas fa-user-shield",
        #     "url": "/admin/",
        #     "groups": ["Admin", "IT Team"]
        # }
    }