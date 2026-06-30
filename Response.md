# API Response Schema

All API responses must follow one of the following envelopes.

---

## Single Resource Response

```json
{
  "success": true,
  "data": {},
  "meta": {},
  "timestamp": "2026-06-30T12:34:56Z"
}
```

### Example

```json
{
  "success": true,
  "data": {
    "uuid": "12345678-1234-1234-1234-123456789012",
    "name": "ABC Ltd"
  },
  "meta": {},
  "timestamp": "2026-06-30T12:34:56Z"
}
```

---

## Collection Response

```json
{
  "success": true,
  "data": [],
  "meta": {
    "pagination": {},
    "filters": {},
    "sorting": {},
    "search": ""
  },
  "timestamp": "2026-06-30T12:34:56Z"
}
```

### Example

```json
{
  "success": true,
  "data": [
    {
      "uuid": "1",
      "name": "ABC Ltd"
    },
    {
      "uuid": "2",
      "name": "XYZ Ltd"
    }
  ],
  "meta": {
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 105,
      "total_pages": 6,
      "has_next": true,
      "has_previous": false
    },
    "filters": {
      "status": "active"
    },
    "sorting": {
      "field": "created_at",
      "direction": "desc"
    },
    "search": "abc"
  },
  "timestamp": "2026-06-30T12:34:56Z"
}
```

---

## Mutation Response (POST, PUT, PATCH, DELETE)

```json
{
  "success": true,
  "message": "Human-readable success message.",
  "data": {},
  "meta": {},
  "timestamp": "2026-06-30T12:34:56Z"
}
```

### Example

```json
{
  "success": true,
  "message": "Company created successfully.",
  "data": {
    "uuid": "12345678-1234-1234-1234-123456789012",
    "name": "ABC Ltd"
  },
  "meta": {},
  "timestamp": "2026-06-30T12:34:56Z"
}
```

---

## Error Response

```json
{
  "success": false,
  "message": "Human-readable error summary.",
  "errors": {},
  "meta": {},
  "timestamp": "2026-06-30T12:34:56Z"
}
```

### Validation Error Example

```json
{
  "success": false,
  "message": "Validation failed.",
  "errors": {
    "email": [
      "This field is required."
    ],
    "phone": [
      "Enter a valid phone number."
    ]
  },
  "meta": {},
  "timestamp": "2026-06-30T12:34:56Z"
}
```

---

## Rules

- `success` must always be present and be a boolean.
- Successful `GET` requests do **not** require a `message`.
- Successful `POST`, `PUT`, `PATCH`, and `DELETE` requests should include a human-readable `message`.
- Failed responses must always include a `message`.
- Single-resource endpoints return an object in `data`.
- Collection endpoints return an array in `data`.
- Failed responses return an `errors` object.
- `meta` must always be present, even if empty.
- `timestamp` must be an ISO-8601 UTC datetime string.
- Pagination, filtering, sorting, search terms, counts, links, and other metadata belong inside `meta`.
- Validation errors should populate `errors` with field-level messages.
- General errors may return an empty `errors` object.
