# PRCS - Property Rate and Collection System

A Django-based property tax and business permit billing system for local municipal authorities (GEMA/LANMA).

## Overview

PRCS is a comprehensive web application for managing property ratings, business operating permits, and revenue collection for municipal assemblies. It provides GIS-based property mapping, bill generation, payment integration, and reporting capabilities.

## Features

- **Property Registry**: GIS-based property management with mapping
- **Business Operating Permits (BOP)**: Business permit billing and tracking
- **Property Rate (PR)**: Property tax billing
- **Bill Generation**: Automated bill creation with customizable rates
- **Payment Integration**: Kowri payment gateway integration
- **Payment Tracking**: Click tracking on payment links
- **Dashboard**: Revenue dashboards and analytics
- **User Management**: Role-based access (Admin, Supervisor, Collector)
- **Rate Management**: Configurable tax/fee rates by category
- **Export**: CSV/Excel export capabilities

## Technology Stack

- **Backend**: Django 6.0.2
- **Database**: PostgreSQL with PostGIS
- **API**: Django REST Framework 3.17.1
- **GIS**: Django Leaflet, PMTiles
- **Frontend**: Bootstrap 5, jQuery, DataTables
- **Admin**: Django Jazzmin

## Project Structure

```
PRCS/
├── PRCS/                 # Django project settings
│   ├── settings.py       # Main configuration
│   ├── urls.py           # URL routing
│   ├── wsgi.py          # WSGI entry
│   └── asgi.py          # ASGI entry
├── core/                 # Main application
│   ├── models.py        # Database models
│   ├── urls.py         # URL routing
│   ├── views/          # View handlers
│   ├── services/      # Business logic
│   ├── templates/      # HTML templates
│   └── management/    # Django management commands
├── api/                 # REST API
│   ├── urls.py
│   ├── views.py
│   ├── serializers.py
│   └── permissions.py
├── billing/             # Billing app
│   ├── models.py
│   ├── urls.py
│   └── views.py
├── templates/          # Shared templates
├── static/             # Static assets
├── media/              # Uploaded files
├── requirements.txt    # Python dependencies
└── manage.py          # Django management
```

## Installation

### Prerequisites

- Python 3.10+
- PostgreSQL 14+ with PostGIS extension
- Redis (for caching)

### Setup

1. **Clone and create virtual environment**:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configure environment variables**:
```bash
cp .env.example .env
# Edit .env with your settings
```

4. **Run migrations**:
```bash
python manage.py migrate
```

5. **Create superuser**:
```bash
python manage.py createsuperuser
```

6. **Run development server**:
```bash
python manage.py runserver
```

## Database Configuration

The project uses two PostgreSQL databases:
- `gema_new_db` - Main database
- `property_rate` - Property rate data

Update `DATABASES` in `PRCS/settings.py` for your setup.

## Management Commands

```bash
# Generate PMTiles for maps
python manage.py generate_pmtiles_vectors

# Generate property PMTiles
python manage.py generate_properties_pmtiles

# Convert vector data
python manage.py vector_conversion

# Complete vector conversion
python manage.py complete_converter_vector
```

## API Endpoints

### Property Registry
- `GET /api/properties/list/` - List properties
- `POST /api/properties/create/` - Create property
- `GET /api/properties/<id>/` - Get property details
- `PUT /api/properties/<id>/update/` - Update property
- `DELETE /api/properties/<id>/delete/` - Delete property

### Billing
- `GET /api/bills/` - List bills
- `POST /api/bills/generate/` - Generate bill
- `POST /api/bops-bills/generate/` - Generate BOP bills
- `GET /api/calculate-tax/` - Calculate tax

### Payments
- `GET /api/payments/kowri/lookup/` - Kowri bill lookup
- `POST /api/payments/kowri/notification/` - Payment notification
- `GET /api/payments/status/<type>/<id>/` - Payment status

### Maps
- `GET /api/properties/geojson/` - Property GeoJSON
- `GET /api/zones/geojson/` - Zone GeoJSON
- `GET /api/bops/geojson/` - BOP GeoJSON

## User Roles

| Role | Description |
|------|-----------|
| Admin | Full system access |
| Supervisor | Review and manage collectors |
| Collector | Property data collection |
| Client | External access (future) |

## Models

### Core Models

- **UserModel**: Staff/collector accounts
- **Polygon**: Spatial property polygons
- **Session**: Field data collection sessions
- **PREntry**: Property rate entries
- **BOPEntry**: Business permit entries
- **Business**: Business entities
- **BusinessType/SubType/Category**: Business classification

### Billing Models

- **Bill**: Financial bills
- **Payment**: Payment records
- **PaymentLinkClick**: Click tracking
- **FeeSchedule**: Rate configuration

### System Models

- **LookupGroup/LookupValue**: Lookup tables
- **SystemSetting**: Configuration
- **OTPCode**: Authentication
- **AuditLog**: Activity logging
- **Notification**: Messages

## Template Structure

Templates use a modular structure:
- `templates/main/base.html` - Base template
- `templates/partials/` - Reusable components
- `core/templates/core/main/` - Feature templates

## Settings

Key settings in `PRCS/settings.py`:

```python
DEBUG = True
ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'gema_new_db',
        ...
    }
}

# Email configuration
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 465

# JWT settings
JWT_SECRET_KEY = 'your-secret-key'
JWT_ACCESS_TOKEN_LIFETIME = 900

# Payment gateway
KOWRI_WEBHOOK_SECRET = 'your-secret'
```

## Development

### Running Tests
```bash
python manage.py test
```

### Creating Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Loading Sample Data
```bash
python manage.pyloaddata fixtures.json
```

## Production Deployment

1. Set `DEBUG = False` in settings
2. Configure proper ALLOWED_HOSTS
3. Set up reverse proxy (nginx)
4. Configure Redis for caching
5. Set up gunicorn/uvicorn
6. Configure HTTPS
7. Set up scheduled tasks for bill generation

## Troubleshooting

### Common Issues

- **PostGIS not installed**: Install PostGIS extension in PostgreSQL
- **Redis connection**: Ensure Redis is running
- **Map tiles not loading**: Check PMTiles generation
- **Payment failures**: Verify Kowri configuration

### Logs

Check `logs/django.log` for errors.

## License

Proprietary - All rights reserved

## Support

For issues and feature requests, contact the development team.

## Credits

Built with Django, PostgreSQL, PostGIS, and Leaflet.

---

# Geospatial Implementation

## Overview

PRCS includes comprehensive GIS (Geographic Information System) capabilities for property mapping, spatial analysis, and visualization. The system uses PostGIS for spatial data storage and PMTiles for efficient vector tile delivery to the frontend.

## Architecture

```
Database (PostGIS) → Django Models → PMTiles Generation → Frontend (Leaflet/MapLibre)
```

## Database Models with Spatial Fields

### Polygon Model

The core spatial model stores property boundaries:

```python
class Polygon(models.Model):
    division    = models.IntegerField()
    block       = models.IntegerField()
    property    = models.IntegerField()
    g_code      = models.CharField(max_length=100, unique=True)  # Global code (e.g., "010-05-001")
    area_in_me  = models.FloatField()  # Area in square meters
    
    # Address fields
    district    = models.CharField(max_length=100)
    postcode    = models.CharField(max_length=100)
    address     = models.CharField(max_length=100)
    street      = models.CharField(max_length=100)
    region      = models.CharField(max_length=100)
    
    # Coordinates
    latitude    = models.FloatField()
    longitude   = models.FloatField()
    
    # Spatial boundaries (for properties without stored geometry)
    nlat        = models.FloatField()  # North latitude
    slat        = models.FloatField()  # South latitude
    wlong       = models.FloatField() # West longitude
    elong       = models.FloatField()  # East longitude
    
    # PostGIS geometry field
    geom        = models.GeometryField(srid=4326)
    
    status      = models.CharField(choices=PolygonStatus.choices)
```

### Business Model

Business locations with spatial data:

```python
class Business(models.Model):
    account_number  = models.CharField(max_length=100, unique=True)
    business_name   = models.CharField(max_length=255)
    
    # Address
    location        = models.CharField(max_length=255)
    address         = models.TextField()
    digital_address = models.CharField(max_length=100)
    house_number    = models.CharField(max_length=100)
    
    # Coordinates
    lng = models.DecimalField(max_digits=15, decimal_places=12)
    lat = models.DecimalField(max_digits=15, decimal_places=12)
    
    # Geometry (stored as PostGIS point)
    geometry = models.GeometryField(srid=4326)  # WGS84
    
    # Foreign keys to business classification
    business_type = models.ForeignKey(BusinessType, ...)
    business_sub_type = models.ForeignKey(BusinessSubType, ...)
    business_category_value = models.ForeignKey(BusinessCategory, ...)
```

## PMTiles Generation

### Command Overview

The project includes a management command to generate vector tiles from database geometries:

```bash
python manage.py generate_pmtiles_vectors --output properties.pmtiles --max-zoom 14 --min-zoom 8 --quality medium
```

### Features

1. **Multiple Geometry Sources**: Extracts geometry in order of preference:
   - PostGIS `geom` field (GeoJSON)
   - Bounding coordinates (nlat, slat, wlong, elong)
   - Point coordinates (latitude, longitude)

2. **Quality Presets**:
   - `draft`: Maximum simplification (20), smallest tiles
   - `low`: High simplification (10)
   - `medium`: Balanced (5) - **default**
   - `high`: Low simplification (2), larger tiles
   - `maximum`: No simplification, full detail

3. **Optimization Flags**:
   - `--detect-shared-borders`: Merge adjacent polygons
   - `--drop-densest-as-needed`: Remove dense features
   - `--coalesce`: Combine small features
   - `--no-tile-size-limit`: Allow larger tiles at high zoom

4. **Output**: Binary PMTiles format (~50-80% compression vs GeoJSON)

### Implementation Details

```python
# core/management/commands/generate_pmtiles_vectors.py

def safe_get_geojson(self, property_obj):
    """Safely extract GeoJSON from property geometry"""
    
    # Method 1: Try geom field with geojson property
    if property_obj.geom:
        try:
            geom_json = property_obj.geom.geojson
            if geom_json:
                return json.loads(geom_json)
        except:
            pass
    
    # Method 2: Create from bounding coordinates
    if all([property_obj.nlat, property_obj.slat, 
           property_obj.wlong, property_obj.elong]):
        coords = [
            [float(property_obj.wlong), float(property_obj.slat)],
            [float(property_obj.elong), float(property_obj.slat)],
            [float(property_obj.elong), float(property_obj.nlat)],
            [float(property_obj.wlong), float(property_obj.nlat)],
            [float(property_obj.wlong), float(property_obj.slat)]
        ]
        return {"type": "Polygon", "coordinates": [coords]}
    
    # Method 3: Create point from lat/long
    if property_obj.latitude and property_obj.longitude:
        return {
            "type": "Point",
            "coordinates": [float(property_obj.longitude), 
                          float(property_obj.latitude)]
        }
```

## Tile Server API

### Endpoints

| Endpoint | Description |
|----------|-------------|
| `/tiles/` | Serve PMTiles with HTTP Range support |
| `/api/properties/points/` | Get point properties for clustering |
| `/api/properties/geojson/simple/` | Get simplified GeoJSON from cache |
| `/api/properties/<id>/geojson/` | Get single property GeoJSON |
| `/api/properties/geojson/` | Full property GeoJSON |
| `/api/zones/geojson/` | Zone boundaries |
| `/api/districts/geojson/` | District boundaries |
| `/api/bops/geojson/` | Business locations |

### PMTiles HTTP Serving

```python
# core/views/views_tiles.py

@require_http_methods(["GET", "HEAD"])
@cache_control(max_age=86400, public=True)
def serve_pmtiles(request, filename):
    """Serve PMTiles with HTTP Byte Serving support"""
    
    # Security: whitelist allowed files
    ALLOWED_PMTILES_FILES = [
        'properties_high_quality_v1.pmtiles',
        'aerial_imagery_v1.pmtiles',
    ]
    
    # Support HTTP Range requests for partial content
    # Handle If-Modified-Since and ETag headers
    # Cache for 24 hours
```

### Caching Strategy

The GeoJSON API uses Redis caching:

```python
def properties_simple_geojson(request):
    """Return simplified GeoJSON from cache"""
    
    # Check if loading is in progress
    if cache.get('properties_loading'):
        return JsonResponse({
            "status": "loading",
            "progress": cache.get('properties_geojson_partial')
        }, status=202)
    
    # Get from cache
    geojson_data = cache.get('properties_geojson_final')
    return JsonResponse(geojson_data)
```

## Frontend Map Integration

### Template Structure

The map interface is built with:

- **Map Library**: Leaflet.js with MapLibre GL JS fallback
- **Tile Protocol**: PMTiles protocol for vector tile loading
- **Base Layers**: Custom PMTiles + OpenStreetMap
- **Interactive Elements**: Property markers, zones, districts

### Map Features

1. **Property Visualization**:
   - Polygon overlays from PMTiles
   - Point clustering at low zoom
   - Individual property highlighting

2. **Search & Filter**:
   - Spatial search by district/zone
   - Property type filtering
   - Real-time search suggestions

3. **Data Collection**:
   - GPS location capture
   - Boundary mapping
   - Offline capability

4. **Analysis Tools**:
   - Zone performance visualization
   - Heat map generation
   - Area statistics

### Example Map Initialization

```javascript
// Initialize PMTiles layer
const pmtilesUrl = '/tiles/properties_high_quality_v1.pmtiles';
const pmTiles = new PMTiles(pmtilesUrl);

// Create Leaflet map
const map = L.map('map').setView([5.6037, -0.1870], 14); // Accra, Ghana

// Add PMTiles source
const layer = new L.PMTilesLayer({
    url: pmtilesUrl,
    style: {
        fillColor: '#0dae48',
        fillOpacity: 0.3,
        color: '#0a8d3a',
        weight: 1
    }
}).addTo(map);
```

## GIS Data Import

### Vector Data Processing

The project includes commands for converting external GIS data:

```bash
# Convert various formats to PostGIS
python manage.py vector_conversion
python manage.py complete_converter_vector

# Generate PMTiles after import
python manage.py generate_properties_pmtiles
```

### Supported Formats

- GeoJSON (import/export)
- Shapefile (via GDAL/OGR)
- KML/KMZ
- GPX ( GPS data)

## Performance Optimization

### Strategies Used

1. **PMTiles**: Binary vector tiles (~50-80% smaller)
2. **Caching**: Redis for frequently accessed GeoJSON
3. **HTTP Range**: Partial tile requests
4. **CDN Ready**: 24-hour cache headers
5. **Database Indexes**: On spatial columns

### Index Configuration

```python
# Spatial indexes are automatically created for GeometryField
class Meta:
    indexes = [
        models.Index(fields=['geom'], using='gist'),
    ]
```

## Future Enhancements

1. **Server-side Rendering**: Vector tile styling on demand
2. **Real-time Updates**: Hot reload of changed geometries
3. **Offline Maps**: Service worker for field data collection
4. **3D Support**: Building height visualization
5. **Advanced Analysis**: Spatial joins, buffer zones