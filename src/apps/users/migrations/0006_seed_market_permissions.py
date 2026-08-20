from django.db import migrations

from apps.common.ids import generate_unique_public_id


MARKET_PERMISSIONS = [
    ("markets.list", "List markets", "List markets."),
    ("markets.create", "Create markets", "Create markets."),
    ("markets.read", "Read markets", "Read market details."),
    ("markets.update", "Update markets", "Update markets."),
    ("markets.delete", "Delete markets", "Delete markets."),
    ("market_prices.list", "List market prices", "List market commodity prices."),
    ("market_prices.create", "Create market prices", "Create market commodity prices."),
    ("market_prices.read", "Read market prices", "Read market commodity price details."),
    ("market_prices.update", "Update market prices", "Update market commodity prices."),
    ("market_prices.delete", "Delete market prices", "Delete market commodity prices."),
    ("market_prices.latest", "View latest market prices", "View latest prices for commodities in a market."),
    ("commodity_prices.list", "List commodity prices", "List prices for a commodity across markets."),
    ("commodity_prices.history", "View commodity price history", "View commodity price history across markets."),
    ("commodity_prices.compare", "Compare commodity prices", "Compare commodity prices across markets."),
]

DEFAULT_MARKET_ROLE_PERMISSIONS = {
    "admin": [code for code, _name, _description in MARKET_PERMISSIONS],
    "farmer": [
        "markets.list",
        "markets.read",
        "market_prices.list",
        "market_prices.read",
        "market_prices.latest",
        "commodity_prices.list",
        "commodity_prices.history",
        "commodity_prices.compare",
    ],
    "entrepreneur": [
        "markets.list",
        "markets.read",
        "market_prices.list",
        "market_prices.read",
        "market_prices.latest",
        "commodity_prices.list",
        "commodity_prices.history",
        "commodity_prices.compare",
    ],
    "buyer": [
        "markets.list",
        "markets.read",
        "market_prices.list",
        "market_prices.read",
        "market_prices.latest",
        "commodity_prices.list",
        "commodity_prices.history",
        "commodity_prices.compare",
    ],
    "market_officer": [
        "markets.list",
        "markets.read",
        "market_prices.list",
        "market_prices.create",
        "market_prices.read",
        "market_prices.update",
        "market_prices.latest",
        "commodity_prices.list",
        "commodity_prices.history",
        "commodity_prices.compare",
    ],
}


def seed_market_permissions(apps, schema_editor):
    Permission = apps.get_model("users", "Permission")
    Role = apps.get_model("users", "Role")
    RolePermission = apps.get_model("users", "RolePermission")

    permissions = []
    for code, name, description in MARKET_PERMISSIONS:
        permission = Permission.objects.filter(code=code).first()
        if permission is None:
            permission = Permission(
                public_id=generate_unique_public_id(Permission),
                code=code,
                name=name,
                description=description,
            )
            permission.save()
        else:
            permission.name = name
            permission.description = description
            permission.save(update_fields=["name", "description"])
        permissions.append(permission)

    permissions_by_code = {permission.code: permission for permission in permissions}

    role_permissions = []
    for role_code, permission_codes in DEFAULT_MARKET_ROLE_PERMISSIONS.items():
        role = Role.objects.filter(code=role_code).first()
        if role is None:
            continue
        role_permissions.extend(
            RolePermission(role=role, permission=permissions_by_code[permission_code])
            for permission_code in permission_codes
            if permission_code in permissions_by_code
        )

    RolePermission.objects.bulk_create(role_permissions, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0005_remove_researcher_role"),
    ]

    operations = [
        migrations.RunPython(seed_market_permissions, migrations.RunPython.noop),
    ]
