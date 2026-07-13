# Bulk Area Import Schema

Use `POST {{base_url}}/api/v1/areas/bulk` for path-based area imports.

The backend finds existing areas by path or creates missing parents automatically.

## Region

```json
{
  "level": "region",
  "path": ["Morogoro"]
}
```

## District

```json
{
  "level": "district",
  "path": ["Morogoro", "Kilombero"]
}
```

## Ward

```json
{
  "level": "ward",
  "path": ["Morogoro", "Kilombero", "Ifakara"]
}
```

Rules:

- Do not send `parent_id` to the bulk import endpoint.
- `region` requires path length 1.
- `district` requires path length 2.
- `ward` requires path length 3.
- Missing parent areas are created automatically.
- Duplicate paths are not created again. They are returned in `data.skipped` with reason `duplicate`.
- Successfully created rows are returned in `data.created`.
- Rows that fail unexpectedly are returned in `data.failed`, while other valid rows can still be created.

Response shape:

```json
{
  "success": true,
  "message": "Administrative area bulk import completed.",
  "data": {
    "created": [],
    "skipped": [
      {
        "reason": "duplicate",
        "message": "Area path already exists.",
        "path": ["Morogoro", "Kilombero", "Ifakara"]
      }
    ],
    "failed": []
  },
  "meta": {
    "created_count": 0,
    "skipped_count": 1,
    "failed_count": 0
  }
}
```
