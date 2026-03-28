# GEMA Mobile App — API Endpoint Documentation

Base URL: `{API_URL}`

---

## Authentication

All endpoints (except login) require a Bearer token in the Authorization header:

```
Authorization: Bearer <accessToken>
```

Access tokens expire after **15 minutes**. Use the refresh endpoint to get a new one.

---

## 1. Login

### `POST /auth/login`

**Auth:** None

**Request:**
```json
{
  "employeeId": "EA001",
  "password": "string",
  "expoPushToken": "ExponentPushToken[xxxxxx]  (optional)"
}
```

> If `expoPushToken` is provided, it is saved on the user record for server-initiated push notifications (e.g., session approved/rejected alerts).

**Response (200):**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "uuid",
      "employeeId": "EA001",
      "name": "John Doe",
      "email": "john@example.com",
      "phone": "0241234567",
      "role": "collector",
      "supervisorId": "uuid | null",
      "isActive": true,
      "createdAt": "2026-01-01T00:00:00.000Z",
      "updatedAt": "2026-01-01T00:00:00.000Z"
    },
    "tokens": {
      "accessToken": "eyJhbG...",
      "refreshToken": "eyJhbG..."
    }
  }
}
```

**Error (401):**
```json
{
  "success": false,
  "error": "Invalid credentials"
}
```

---

## 2. Refresh Token

### `POST /auth/refresh`

**Auth:** None

**Request:**
```json
{
  "refreshToken": "eyJhbG..."
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "accessToken": "eyJhbG... (new)",
    "refreshToken": "eyJhbG... (new, rotated)"
  }
}
```

**Error (401):**
```json
{
  "success": false,
  "error": "Invalid or expired refresh token"
}
```

> **Note:** Refresh tokens are single-use. Each refresh returns a new refresh token and invalidates the old one.

---

## 3. Logout

### `POST /auth/logout`

**Auth:** Required (collector)

**Request:** No body needed.

**Response (200):**
```json
{
  "success": true,
  "message": "Logged out"
}
```

---

## 4. Change Password

### `POST /auth/change-password`

**Auth:** Required (collector)

**Request:**
```json
{
  "currentPassword": "string (min 1 char)",
  "newPassword": "string (min 6 chars)"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Password changed successfully"
}
```

**Error (400):**
```json
{
  "success": false,
  "error": "Current password is incorrect"
}
```

---

## 5. Fetch Assigned Polygons (with Delta Sync)

### `GET /sync/assignments/:collectorId`

**Auth:** Required (collector can only fetch their own assignments)

**Query Params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `updatedSince` | ISO8601 string | No | Only return polygons updated after this timestamp (for delta sync) |

**Example:** `GET /sync/assignments/abc-uuid-123?updatedSince=2026-03-10T00:00:00.000Z`

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "GEMA15001001",
      "division": 15,
      "block": 1,
      "property": 1,
      "location": "D15B001",
      "status": "unvisited",
      "accessed": false,
      "latitude": 5.647637,
      "longitude": -0.231333,
      "coordinates": [
        { "latitude": 5.647571, "longitude": -0.231234 },
        { "latitude": 5.647531, "longitude": -0.231291 },
        { "latitude": 5.647598, "longitude": -0.231341 },
        { "latitude": 5.647571, "longitude": -0.231234 }
      ],
      "updatedAt": "2026-03-10T12:56:42.373Z"
    }
  ],
  "assignedPolygonIds": ["GEMA15001001", "PS15001002", "..."]
}
```

**Error (403):**
```json
{
  "success": false,
  "error": "Cannot access other collector assignments"
}
```

### Polygon Status Values

| Status | Description |
|--------|-------------|
| `unvisited` | Not yet visited by collector |
| `complete` | Data collection complete (PR with owners) |
| `partial` | Partial data collected |
| `passed` | Collector could not access property |
| `draft` | Draft submission |
| `assessed` | Already assessed from Excel import — **collector should skip these** |

### Delta Sync Flow

1. **First sync:** Call without `updatedSince` → get all assigned polygons
2. **Subsequent syncs:** Pass the latest `updatedAt` timestamp from local DB → only get changed polygons
3. Use `assignedPolygonIds` array to detect unassigned polygons (remove locally if not in list)

---

## 6. Submit Collected Data (Sync Batch)

### `POST /sync/batch`

**Auth:** Required (collector only)

This is the main data submission endpoint. The mobile app queues submissions locally and sends them in batches.

**Request:**
```json
{
  "items": [
    {
      "id": "uuid (client-generated request ID)",
      "polygonId": "GEMA15001001",
      "sessionId": "uuid (client-generated, required for 'submit')",
      "action": "submit",
      "data": {
        "pr": {
          "mode": "owners",
          "entries": [
            {
              "ownerName": "John Doe",
              "contact": "0241234567",
              "ghanaCard": "GHA-123456789-0",
              "email": "john@example.com",
              "gpsAddr": "GA-123-4567",
              "streetName": "Kwabenya Road",
              "title": 2,
              "titleOther": "",
              "loc": 1,
              "locOther": "",
              "propType": 0,
              "propTypeOther": "",
              "propState": 0,
              "stories": 1,
              "rooms": 3,
              "occupier": 0,
              "occupierOther": "",
              "msgMethod": 2,
              "payMethod": 2,
              "titleStr": "Mr.",
              "locStr": "Kwabenya",
              "typeStr": "Residential",
              "stateStr": "Completed",
              "storiesStr": "1 Story",
              "occupierStr": "Owner",
              "msgMethodStr": "WhatsApp",
              "payMethodStr": "Mobile Money"
            }
          ]
        },
        "businesses": [
          {
            "mode": "owner",
            "data": {
              "structOwner": "Jane Doe",
              "title": 3,
              "titleOther": "",
              "bizOwner": "Jane Doe",
              "tin": "C0012345678",
              "contact": "0209876543",
              "email": "jane@example.com",
              "age": "35",
              "gender": 1,
              "bizName": "ABC Shop",
              "bizType": "Retail Trading",
              "bizSubType": "General Goods",
              "category": "A",
              "nature": 0,
              "natureOther": "",
              "structure": 0,
              "structureOther": "",
              "loc": 1,
              "locOther": "",
              "landmark": "Near Kwabenya Junction",
              "gpsAddr": "GA-123-4568",
              "permitNo": "BOP-2025-001",
              "msgMethod": 1,
              "payMethod": 2,
              "titleStr": "Mrs.",
              "natureStr": "Sole Proprietorship",
              "structStr": "Block",
              "locStr": "Kwabenya",
              "msgMethodStr": "SMS",
              "payMethodStr": "Mobile Money"
            }
          }
        ],
        "location": {
          "status": "verified",
          "latitude": 5.647637,
          "longitude": -0.231333,
          "accuracy": 8.5,
          "timestamp": "2026-03-10T14:30:00.000Z",
          "isMocked": false,
          "distanceToPolygon": 12.5
        }
      },
      "collectorId": "collector-uuid",
      "submittedAt": "2026-03-10T14:35:00.000Z"
    }
  ]
}
```

### Item Actions

#### `"action": "submit"` — Submit property/business data

Requires `sessionId` (client-generated UUID for idempotency).

The `data` object contains:

| Field | Type | Description |
|-------|------|-------------|
| `data.pr` | object \| null | Property register data (see PR Data section below) |
| `data.pr.mode` | string | `"owners"`, `"poc"`, `"skip"`, or `"na"` |
| `data.businesses` | array | Array of business entry objects (see BOP Data section below) |
| `data.businesses[].mode` | string | `"owner"` (owner present) or `"poc"` (point of contact) |
| `data.businesses[].data` | object | BOP form fields (resolved, with `*Str` string equivalents) |
| `data.location` | object \| null | Geofence verification data |

#### `"action": "pass"` — Mark property as inaccessible

No `sessionId` needed. No `data` required (can be empty `{}`).

```json
{
  "id": "uuid",
  "polygonId": "GEMA15001001",
  "action": "pass",
  "data": {},
  "collectorId": "collector-uuid",
  "submittedAt": "2026-03-10T14:35:00.000Z"
}
```

### Location Verification Object

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"verified"` (inside polygon), `"proximity"` (within 50m), `"unverified"` (>50m away), `"mocked"` (GPS spoofing detected) |
| `latitude` | number | Collector's GPS latitude |
| `longitude` | number | Collector's GPS longitude |
| `accuracy` | number | GPS accuracy in meters |
| `timestamp` | ISO8601 | When location was captured |
| `isMocked` | boolean | Whether mock location was detected |
| `distanceToPolygon` | number | Distance in meters from polygon centroid |

**Response (200):**
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "id": "request-uuid-1",
        "status": "accepted",
        "message": null
      },
      {
        "id": "request-uuid-2",
        "status": "duplicate",
        "message": "Session already exists"
      },
      {
        "id": "request-uuid-3",
        "status": "error",
        "message": "Processing failed"
      }
    ]
  }
}
```

### Result Statuses

| Status | Meaning | Mobile Action |
|--------|---------|---------------|
| `accepted` | Successfully processed | Remove from sync queue |
| `duplicate` | Session already exists (idempotent) | Remove from sync queue (already synced) |
| `error` | Processing failed | Keep in queue, retry later |

### Idempotency

- `sessionId` is the idempotency key — submitting the same `sessionId` twice returns `duplicate` (no data corruption)
- `id` is the request ID — used to match results back to queue items
- If a polygon already has a session, the old session is soft-deleted and replaced with the new one

### Side Effects on Submit

| Action | Polygon Status Change |
|--------|----------------------|
| `submit` with PR mode `"owners"` or `"na"` | → `complete` |
| `submit` with other PR mode | → `partial` |
| `pass` | → `passed` |

---

### PR Data Structure

The `data.pr` object varies by mode:

#### Mode: `"owners"` — Property owner(s) present

Multiple owners can be recorded per property. Uses `entries` array (not `data`).

```json
{
  "mode": "owners",
  "entries": [ { /* PrOwnerEntry fields below */ } ]
}
```

**PR Owner Entry Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ownerName` | string | Yes | Full name of property owner |
| `contact` | string | Yes | Phone number |
| `ghanaCard` | string | No | Ghana Card number |
| `email` | string | No | Email address |
| `gpsAddr` | string | No | GPS address (e.g., GA-123-4567) |
| `streetName` | string | No | Street or road name |
| `title` | number | Yes | Title index (see Lookup Values) |
| `titleOther` | string | No | Custom title if "Others" selected |
| `loc` | number | Yes | Location index (see Lookup Values) |
| `locOther` | string | No | Custom location if "Others" selected |
| `propType` | number | Yes | Property type index |
| `propTypeOther` | string | No | Custom property type if "Others" |
| `propState` | number | Yes | Property state index |
| `stories` | number | Yes | Stories index |
| `rooms` | number | Yes | Room count index (0=1 room, 11=12 rooms) |
| `occupier` | number | Yes | Occupier type index |
| `occupierOther` | string | No | Custom occupier if "Other" |
| `msgMethod` | number | Yes | Preferred messaging method index |
| `payMethod` | number | Yes | Preferred payment method index |

**Resolved string fields** (auto-appended by mobile app):

`titleStr`, `locStr`, `typeStr`, `stateStr`, `storiesStr`, `occupierStr`, `msgMethodStr`, `payMethodStr`

#### Mode: `"poc"` — Point of contact (owner unavailable)

Single POC record. Uses `data` object.

```json
{
  "mode": "poc",
  "data": { /* PrPocResolved fields below */ }
}
```

**PR POC Fields** (all PR Owner fields above, plus):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pocName` | string | Yes | Name of contact person |
| `pocContact` | string | Yes | Contact person's phone number |
| `pocRel` | number | Yes | Relationship index (see Lookup Values) |
| `pocRelOther` | string | No | Custom relationship if "Other" |

> Note: POC form does NOT include `occupier`/`occupierOther` fields. Adds resolved `relStr`.

#### Mode: `"skip"` — PR skipped

```json
{
  "mode": "skip",
  "data": {
    "reason": "Owner lives abroad",
    "notes": "Optional collector notes"
  }
}
```

Skip reasons: `Owner lives abroad`, `Property locked`, `Tenant refused info`, `Owner deceased`, `Other`

#### Mode: `"na"` — Not applicable

```json
{
  "mode": "na",
  "data": {
    "reason": "Vacant Plot"
  }
}
```

---

### BOP Data Structure

Each entry in the `data.businesses` array has a `mode` and `data`:

```json
{
  "mode": "owner",
  "data": { /* BopOwnerResolved or BopPocResolved fields */ }
}
```

#### Mode: `"owner"` — Business owner present

**BOP Owner Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `structOwner` | string | Yes | Structure/property owner name |
| `title` | number | Yes | Title index |
| `titleOther` | string | No | Custom title if "Others" |
| `bizOwner` | string | Yes | Business owner name (may differ from structure owner) |
| `tin` | string | No | TIN or Ghana Card number |
| `contact` | string | Yes | Phone number |
| `email` | string | No | Email address |
| `age` | string | No | Age (numeric string) |
| `gender` | number | Yes | `0` = Male, `1` = Female |
| `bizName` | string | No | Business name |
| `bizType` | string | Yes | Business type name from the rate schedule (207 types — see Business Type Reference below) |
| `bizSubType` | string | No | Sub-type within the business type (only some types have sub-types) |
| `category` | string | No | Rate category label (e.g., "CAT A - Large Scale", "CAT B - Medium") |
| `nature` | number | Yes | Nature of business index |
| `natureOther` | string | No | Custom nature if "Other" |
| `structure` | number | Yes | Business structure index |
| `structureOther` | string | No | Custom structure if "Other" |
| `loc` | number | Yes | Location index |
| `locOther` | string | No | Custom location if "Others" |
| `landmark` | string | No | Nearby landmark |
| `gpsAddr` | string | No | GPS address |
| `permitNo` | string | No | Existing BOP permit number |
| `msgMethod` | number | No | Preferred messaging method index |
| `payMethod` | number | No | Preferred payment method index |

**Resolved string fields:** `titleStr`, `natureStr`, `structStr`, `locStr`, `msgMethodStr`, `payMethodStr`

#### Mode: `"poc"` — Point of contact for business

**BOP POC Fields** (all BOP Owner fields above, plus):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pocName` | string | Yes | Point of contact name |
| `pocContact` | string | Yes | POC phone number |
| `pocRel` | number | Yes | Relationship index (BOP-specific, see Lookup Values) |
| `pocRelOther` | string | No | Custom relationship if "Other" |

**Resolved string fields:** adds `relStr` to the owner resolved fields.

---

### Lookup Values (Index → String Mapping)

All numeric fields above are zero-based indexes into these arrays:

**Titles** (`title`): `[0] Prof.`, `[1] Dr.`, `[2] Mr.`, `[3] Mrs.`, `[4] Master.`, `[5] Miss.`, `[6] Others`

**Locations** (`loc`): `[0] Ashongman Estate`, `[1] Kwabenya`, `[2] Haatso`, `[3] Agbogba Cosway`, `[4] Dome`, `[5] Abokobi`, `[6] Sesemi`, `[7] West Legon`, `[8] Taifa`, `[9] Ashongman Village`, `[10] Akatsi Abor`, `[11] Haatso Boshe`, `[12] Others`

**Property Types** (`propType`): `[0] Residential`, `[1] Commercial`, `[2] Mixed Use`, `[3] School`, `[4] Others`

**Property States** (`propState`): `[0] Completed`, `[1] Uncompleted`, `[2] Under-Construction`, `[3] Vacant Plot`

**Stories** (`stories`): `[0] Ground Bldg`, `[1] 1 Story`, `[2] 2 Story`, `[3] 3 Story`, `[4] 4 Story`, `[5] 5 Story`

**Occupiers** (`occupier`, PR only): `[0] Owner`, `[1] Tenant`, `[2] Care Taker`, `[3] Other`

**PR POC Relationships** (`pocRel`, PR): `[0] Tenant`, `[1] Security`, `[2] Relative`, `[3] Neighbor`, `[4] Employee`, `[5] Other`

**Business Natures** (`nature`): `[0] Sole Proprietorship`, `[1] Partnership`, `[2] Limited Liability`, `[3] Other`

**Business Structures** (`structure`): `[0] Block`, `[1] Container`, `[2] Kiosk`, `[3] Other`

**BOP POC Relationships** (`pocRel`, BOP): `[0] Attendant`, `[1] Employee`, `[2] Partner`, `[3] Relative`, `[4] Other`

**Messaging Methods** (`msgMethod`): `[0] Email`, `[1] SMS`, `[2] WhatsApp`

**Payment Methods** (`payMethod`): `[0] Bank Transfer`, `[1] Cash`, `[2] Mobile Money`, `[3] USSD`

**Pass Reasons** (action `"pass"`): `Property Locked`, `No Occupants`, `Inaccessible`, `Dangerous`, `Demolished`, `Other`

> **Important:** The mobile app sends both the numeric index AND the resolved string (e.g., `title: 2` + `titleStr: "Mr."`). The backend should store the full JSON as-is in the `pr_data` and `businesses` JSONB columns. Use the `*Str` fields for display; use the numeric indexes if you need to re-map or validate.

### Business Type Reference (`bizType`, `bizSubType`, `category`)

There are **207 business types** in the GA East Municipal Assembly fee schedule. The mobile app presents these as a searchable picker. The three fields work together:

**Structure:**
- `bizType` — the business type name string (e.g., `"Bakeries"`, `"Hotels/Guest Houses"`, `"Auto Mechanics"`)
- `bizSubType` — only present for types that have sub-categories (e.g., Hotels has `"Hotels"`, `"Guest Houses"`, `"Hostels"`)
- `category` — the rate category label (e.g., `"CAT A - Industrial"`, `"CAT B - Medium"`)

**Two patterns exist:**

1. **Flat types** (most common) — have categories directly:
```
bizType: "Bakeries"  →  category: "CAT A - Industrial" (GHS 500)
                         category: "CAT B - Medium" (GHS 250)
                         category: "CAT C - Small" (GHS 150)
```

2. **Types with sub-types** — require selecting a sub-type first, then category:
```
bizType: "Hotels/Guest Houses"
  → bizSubType: "Hotels"        →  category: "CAT A - 4-5 Star" (GHS 5,200)
  → bizSubType: "Guest Houses"  →  category: "CAT A - Large (20+ Rooms)" (GHS 1,560)
  → bizSubType: "Hostels"       →  category: "CAT C - Small" (GHS 350)
```

**Example business types (sample — not exhaustive):**

| Business Type | Has Sub-types | Example Categories |
|---------------|---------------|-------------------|
| Bakeries | No | Industrial / Medium / Small |
| Auto Mechanics | No | Heavy Duty Earthmoving / Light Duty Vehicles |
| Restaurants | No | Fine Dining / Standard / Fast Food (various sizes) |
| Hotels/Guest Houses | Yes (Hotels, Guest Houses, Hostels) | Star ratings / room counts |
| Fuel/Gas Stations | Yes (Fuel, LPG, Cylinder Retail) | Brand type / scale |
| Educational Institutions | Yes (National, Foreign, Vocational, etc.) | Size-based categories |
| Health Facilities | Yes (Hospitals, Clinics, Pharmacy, etc.) | Size/type-based |
| Building Material Dealers | Yes (Hardware, Finishing, Roofing) | Scale-based |
| Financial Services (Non-Bank) | Yes (Microfinance, Money Lending, Mobile Money, Forex) | Scale-based |
| Transport Services | Yes (Commercial, Trotro, Taxi, Ride Hailing) | Fleet size |

> The complete list of 207 business types with all sub-types, categories, and BOP fee amounts is available in the rate data constants file. The backend does not need to validate against this list — it stores the values as-is from the mobile app. The rate data is used during **billing** (Phase 4) to calculate BOP fees.

---

## 7. Fetch Single Polygon

### `GET /polygons/:id`

**Auth:** Required

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": "GEMA15001001",
    "division": 15,
    "block": 1,
    "property": 1,
    "location": "D15B001",
    "coordinates": [{"latitude": 5.647, "longitude": -0.231}, "..."],
    "latitude": 5.647637,
    "longitude": -0.231333,
    "status": "unvisited",
    "accessed": false,
    "createdAt": "2026-01-01T00:00:00.000Z",
    "updatedAt": "2026-03-10T12:56:42.373Z"
  }
}
```

**Error (404):**
```json
{
  "success": false,
  "error": "Polygon not found"
}
```

---

## 8. Fetch Notifications

### `GET /sync/notifications`

**Auth:** Required (collector)

Returns in-app notifications for the logged-in collector (session approved/rejected, new assignments, info messages).

**Query Params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `since` | ISO8601 string | No | Only return notifications created after this timestamp |

**Example:** `GET /sync/notifications?since=2026-03-10T00:00:00.000Z`

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "type": "rejected",
      "title": "Session Rejected",
      "body": "Your submission for GEMA15001001 was rejected. Reason: Missing owner contact.",
      "entityId": "session-uuid (optional, links to related entity)",
      "createdAt": "2026-03-11T14:30:00.000Z"
    },
    {
      "type": "approved",
      "title": "Session Approved",
      "body": "Your submission for GEMA15002005 has been approved.",
      "entityId": "session-uuid",
      "createdAt": "2026-03-11T10:00:00.000Z"
    },
    {
      "type": "assignment",
      "title": "New Assignment",
      "body": "You have been assigned Block 5, Division 15 (42 properties).",
      "entityId": null,
      "createdAt": "2026-03-10T09:00:00.000Z"
    }
  ]
}
```

**Notification Types:**

| Type | Trigger |
|------|---------|
| `rejected` | Supervisor/admin rejects a session |
| `approved` | Supervisor/admin approves a session |
| `assignment` | New polygon block assigned to collector |
| `info` | General system messages |

**Limit:** Returns last 50 notifications.

---

## 9. Health Check

### `HEAD /health` or `GET /health`

**Auth:** None

Used by the mobile app to detect online/offline status.

**Response (200):**
```json
{
  "status": "ok",
  "timestamp": "2026-03-12T10:00:00.000Z"
}
```

---

## 10. Settings / Lookups

These endpoints provide server-driven lookup data for mobile form pickers and business type/rate schedules. The mobile app caches these in SQLite and falls back to bundled constants if no cache exists.

### `GET /settings/lookups`

Returns static enum values used across the system. No authentication required.

**Auth:** None

**Response (200):**
```json
{
  "success": true,
  "data": {
    "polygonStatuses": ["unvisited", "complete", "partial", "passed", "draft", "assessed"],
    "sessionStatuses": ["pending", "approved", "rejected"],
    "billTypes": ["pr", "bop"],
    "billStatuses": ["unpaid", "partial", "paid", "overdue"],
    "paymentMethods": ["cash", "momo", "card", "bank_transfer", "ussd"],
    "userRoles": ["admin", "supervisor", "collector"]
  }
}
```

---

### `GET /settings/form-lookups`

Returns all 14 lookup groups used by mobile form pickers.

**Auth:** Required (Bearer token)

**Query Params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `updatedSince` | ISO 8601 timestamp | No | Only return groups updated after this timestamp for delta sync |

**Response (200):**
```json
{
  "success": true,
  "data": {
    "version": "2026-03-12T10:00:00Z",
    "groups": [
      {
        "slug": "titles",
        "label": "Titles",
        "allowsCustom": true,
        "values": [
          { "slug": "prof", "label": "Prof.", "sortOrder": 0 },
          { "slug": "dr", "label": "Dr.", "sortOrder": 1 },
          { "slug": "mr", "label": "Mr.", "sortOrder": 2 },
          { "slug": "mrs", "label": "Mrs.", "sortOrder": 3 },
          { "slug": "master", "label": "Master.", "sortOrder": 4 },
          { "slug": "miss", "label": "Miss.", "sortOrder": 5 },
          { "slug": "others", "label": "Others", "sortOrder": 6 }
        ]
      }
    ]
  }
}
```

**Lookup Groups (14 total):**

| Group Slug | Label | Allows Custom | Used By |
|-----------|-------|---------------|---------|
| `titles` | Titles | Yes | PR owner, PR POC, BOP owner, BOP POC |
| `locations` | Locations | Yes | PR owner, PR POC, BOP owner, BOP POC |
| `prop_types` | Property Types | Yes | PR owner, PR POC |
| `prop_states` | Property States | No | PR owner, PR POC |
| `stories` | Stories | No | PR owner, PR POC |
| `occupiers` | Occupiers | Yes | PR owner |
| `poc_rels` | POC Relationships | Yes | PR POC |
| `natures` | Nature of Business | Yes | BOP owner, BOP POC |
| `structures` | Structures | Yes | BOP owner, BOP POC |
| `bop_poc_rels` | BOP POC Relationships | Yes | BOP POC |
| `pass_reasons` | Pass Reasons | Yes | Pass screen |
| `skip_reasons` | Skip Reasons | Yes | PR skip screen |
| `msg_methods` | Messaging Methods | No | All forms |
| `pay_methods` | Payment Methods | No | All forms |

**Notes:**
- `allowsCustom: true` means the last option in the mobile picker is "Other" with a free-text field
- Mobile caches all lookups in SQLite and falls back to bundled constants if no cache exists
- `version` is the latest `updated_at` timestamp across all returned groups

---

### `GET /settings/business-types`

Returns all business types with sub-types, categories, and rate amounts.

**Auth:** Required (Bearer token)

**Query Params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `updatedSince` | ISO 8601 timestamp | No | Only return types updated after this timestamp |

**Response (200):**
```json
{
  "success": true,
  "data": {
    "version": "2026-03-12T10:00:00Z",
    "types": [
      {
        "slug": "bakeries",
        "name": "Bakeries",
        "coaCode": "1422009",
        "duration": "Per Annum",
        "subTypes": null,
        "categories": [
          { "slug": "cat-a-industrial", "label": "CAT A - Industrial", "amount": 500.00, "sortOrder": 0 },
          { "slug": "cat-b-commercial", "label": "CAT B - Commercial", "amount": 400.00, "sortOrder": 1 }
        ]
      },
      {
        "slug": "hotels-guest-houses",
        "name": "Hotels/Guest Houses",
        "coaCode": "1422131",
        "duration": "Per Annum",
        "subTypes": [
          {
            "slug": "hotels",
            "name": "Hotels",
            "categories": [
              { "slug": "cat-a-4-5-star", "label": "CAT A - 4-5 Star", "amount": 5200.00, "sortOrder": 0 }
            ]
          }
        ],
        "categories": null
      }
    ]
  }
}
```

**Notes:**
- Business types either have `subTypes` (with categories per sub-type) or direct `categories`, never both
- Currently 207 business types — see `seed-data.json` at the repo root for the full dataset
- Mobile caches in SQLite and falls back to bundled `rateData.ts` if no cache exists
- `amount` is the annual rate in GHS for that category
- `coaCode` is the Chart of Accounts code used for billing

---

### Backend Database Tables

The following tables are needed to support server-driven lookups and business types:

```sql
-- Lookup groups (14 groups)
CREATE TABLE lookup_groups (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug          VARCHAR(50) UNIQUE NOT NULL,
  label         VARCHAR(100) NOT NULL,
  allows_custom BOOLEAN DEFAULT false,
  sort_order    INTEGER DEFAULT 0,
  updated_at    TIMESTAMPTZ DEFAULT now()
);

-- Lookup values (options within each group)
CREATE TABLE lookup_values (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id      UUID NOT NULL REFERENCES lookup_groups(id),
  slug          VARCHAR(100) NOT NULL,
  label         VARCHAR(150) NOT NULL,
  sort_order    INTEGER DEFAULT 0,
  is_active     BOOLEAN DEFAULT true,
  updated_at    TIMESTAMPTZ DEFAULT now(),
  UNIQUE(group_id, slug)
);

-- Business types (207 types)
CREATE TABLE business_types (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug          VARCHAR(150) UNIQUE NOT NULL,
  name          VARCHAR(200) NOT NULL,
  coa_code      VARCHAR(20) NOT NULL,
  duration      VARCHAR(30) DEFAULT 'Per Annum',
  is_active     BOOLEAN DEFAULT true,
  sort_order    INTEGER DEFAULT 0,
  updated_at    TIMESTAMPTZ DEFAULT now()
);

-- Sub-types (only some business types have these)
CREATE TABLE business_sub_types (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_type_id UUID NOT NULL REFERENCES business_types(id),
  slug             VARCHAR(150) NOT NULL,
  name             VARCHAR(200) NOT NULL,
  sort_order       INTEGER DEFAULT 0,
  is_active        BOOLEAN DEFAULT true,
  updated_at       TIMESTAMPTZ DEFAULT now(),
  UNIQUE(business_type_id, slug)
);

-- Categories with amounts (the rate schedule)
CREATE TABLE business_categories (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_type_id UUID NOT NULL REFERENCES business_types(id),
  sub_type_id      UUID REFERENCES business_sub_types(id),
  slug             VARCHAR(150) NOT NULL,
  label            VARCHAR(200) NOT NULL,
  amount           DECIMAL(12,2) NOT NULL,
  sort_order       INTEGER DEFAULT 0,
  is_active        BOOLEAN DEFAULT true,
  effective_from   DATE NOT NULL DEFAULT CURRENT_DATE,
  effective_to     DATE,
  updated_at       TIMESTAMPTZ DEFAULT now()
);
```

> **Note:** Seed data for all 14 lookup groups and 207 business types is provided in `seed-data.json` at the repo root.

---

## Summary of Mobile Endpoints

| # | Method | Path | Auth | Role | Purpose |
|---|--------|------|------|------|---------|
| 1 | POST | `/auth/login` | No | Any | Login, get tokens (+ optional push token) |
| 2 | POST | `/auth/refresh` | No | Any | Refresh access token |
| 3 | POST | `/auth/logout` | Yes | Any | Logout, invalidate tokens |
| 4 | POST | `/auth/change-password` | Yes | Any | Change password |
| 5 | GET | `/sync/assignments/:collectorId` | Yes | Collector (own only) | Fetch assigned polygons (delta sync) |
| 6 | POST | `/sync/batch` | Yes | Collector | Submit collected data |
| 7 | GET | `/sync/notifications` | Yes | Collector | Fetch in-app notifications |
| 8 | GET | `/polygons/:id` | Yes | Any | Get single polygon details |
| 9 | GET | `/health` | No | Any | Connectivity check |
| 10 | GET | `/settings/lookups` | No | Any | Static enum values |
| 11 | GET | `/settings/form-lookups` | Yes | Any | Dynamic form lookup groups |
| 12 | GET | `/settings/business-types` | Yes | Any | Business types with rates |

---

## Mobile App Data Flow

```
1. Login
   POST /auth/login (with optional expoPushToken)
   → store tokens securely (expo-secure-store)

2. Fetch Lookups & Business Types (on first launch or periodically)
   GET /settings/form-lookups
   GET /settings/business-types
   → cache in local SQLite, fall back to bundled constants

3. Fetch Assignments (initial)
   GET /sync/assignments/{userId}
   → store all polygons in local SQLite

4. Fetch Assignments (delta sync)
   GET /sync/assignments/{userId}?updatedSince={lastSyncTimestamp}
   → update only changed polygons locally

5. Collector fills forms offline
   → save to local sync queue with client-generated UUID

6. Submit data when online
   POST /sync/batch (items from queue)
   → for each result:
     "accepted" or "duplicate" → remove from queue
     "error" → keep in queue for retry

7. Fetch Notifications (periodic or on sync)
   GET /sync/notifications?since={lastFetchTimestamp}
   → show approved/rejected/assignment alerts in-app

8. Token refresh (every 15 min)
   POST /auth/refresh → update stored tokens
   If refresh fails → force re-login

9. Connectivity monitoring
   HEAD /health (every 30s or on app foreground)
   → toggle online/offline UI state
```

---

## Error Response Format

All errors follow this structure:

```json
{
  "success": false,
  "error": "Human-readable error message"
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (validation error) |
| 401 | Unauthorized (missing/expired token, bad credentials) |
| 403 | Forbidden (wrong role, accessing another collector's data) |
| 404 | Not found |
| 500 | Server error |

---

## Notes for Backend Developer

1. **Database**: PostgreSQL 15+ with PostGIS extension (for spatial/geometry queries)
2. **Passwords** are hashed with bcryptjs (12 rounds)
3. **JWT secret** is stored in AWS Secrets Manager — access tokens are 15 min, refresh tokens are 7 days
4. **Polygon IDs** are strings like `GEMA15001001` or `PS15001002` (not UUIDs)
5. **Session IDs** are UUIDs generated by the mobile client (prevents duplicates on retry)
6. **Coordinates** are stored as JSON arrays of `{latitude, longitude}` objects (WGS84 / EPSG:4326)
7. **Soft deletes**: Sessions use `deletedAt` field — queries should filter `WHERE deleted_at IS NULL`
8. **Assessed polygons** (status = `assessed`) should be returned to mobile but the app prevents data entry on them
9. **Push notifications**: The `expo_push_token` column on the `users` table stores Expo push tokens. When a session is approved/rejected or a new assignment is created, the backend should create a `collector_notifications` row AND optionally send an Expo push notification using the stored token
10. **Form data storage**: PR data (`pr_data` JSONB) and businesses (`businesses` JSONB) are stored as-is from the mobile app. The backend does NOT need to parse or validate individual fields — just store the JSON blob
11. **Lookup tables**: The 14 lookup groups and 207 business types should be seeded on first deploy. The mobile app falls back to bundled constants if the API is unreachable, so the server values should match the bundled defaults
12. **Supervisor scoping**: Supervisors should only see/manage collectors assigned to them (`supervisor_id` on users table). Admin sees everything
