# API Endpoints

This document lists the available method-level HTTP endpoints exposed by the Django application router. Each row maps to one endpoint method and includes the database permission code used for UI access management.

Permission notes:

- `Public`: no bearer token or DB permission is required.
- `Staff/Admin`: Django staff/superusers bypass DB permission checks.
- `Owner/participant rule`: DB permission is required first, then object ownership or participation is checked.
- `None`: no DB permission code applies to framework/admin documentation routes.

## Auth

| Method | Path | Permission Code | Auth | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| POST | `/api/v1/auth/register` | Public | None | Working | Register new user and send email verification token. |
| POST | `/api/v1/auth/login` | Public | None | Working | Login with username/email and password. |
| POST | `/api/v1/auth/token/refresh` | Public | None | Working | Refresh access token. |
| POST | `/api/v1/auth/email/verify` | Public | None | Working | Verify registered user email. |
| POST | `/api/v1/auth/email/resend` | Public | None | Working | Resend email verification token. |
| POST | `/api/v1/auth/password/reset/request` | Public | None | Working | Request password reset link. |
| POST | `/api/v1/auth/password/reset/confirm` | Public | None | Working | Reset password with token. |
| GET | `/api/v1/auth/me` | `auth.me` | Bearer token | Working | Get current authenticated user profile. |
| DELETE | `/api/v1/auth/me` | `auth.account.delete` | Bearer token | Working | Delete own authenticated account. |
| POST | `/api/v1/auth/logout` | `auth.logout` | Bearer token | Working | Logout acknowledged; client discards tokens. |

## Users

| Method | Path | Permission Code | Auth | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/users` | `users.list` | Bearer token | Working | List managed users. |
| POST | `/api/v1/users` | `users.create` | Bearer token | Working | Create managed user. |
| GET | `/api/v1/users/{user_id}` | `users.read` | Bearer token | Working | Get managed user by public ID. |
| PATCH | `/api/v1/users/{user_id}` | `users.update` | Bearer token | Working | Update managed user by public ID. |
| DELETE | `/api/v1/users/{user_id}` | `users.delete` | Bearer token | Working | Delete managed user by public ID. |

## Roles and Permissions

| Method | Path | Permission Code | Auth | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/users/roles` | `roles.list` | Bearer token | Working | List roles and assigned permissions. |
| POST | `/api/v1/users/roles` | `roles.create` | Bearer token | Working | Create custom role with optional `permission_ids`. |
| GET | `/api/v1/users/roles/{role_id}` | `roles.read` | Bearer token | Working | Get role by public ID or code. |
| PUT | `/api/v1/users/roles/{role_id}` | `roles.update` | Bearer token | Working | Update role metadata and optional `permission_ids`. |
| PATCH | `/api/v1/users/roles/{role_id}` | `roles.permissions.update` | Bearer token | Working | Replace permissions assigned to a role. |
| DELETE | `/api/v1/users/roles/{role_id}` | `roles.delete` | Bearer token | Working | Delete custom role. |
| GET | `/api/v1/users/permissions` | `permissions.list` | Bearer token | Working | List read-only system-defined permissions. |
| GET | `/api/v1/users/permissions/{permission_id}` | `permissions.read` | Bearer token | Working | Get system permission by public ID. |

## Commodity Categories

| Method | Path | Permission Code | Auth | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/commodities/categories` | `commodities.categories.list` | Bearer token | Working | List commodity categories. |
| POST | `/api/v1/commodities/categories` | `commodities.categories.create` | Bearer token | Working | Create commodity category. |
| GET | `/api/v1/commodities/categories/{category_id}` | `commodities.categories.read` | Bearer token | Working | Get commodity category by public ID. |
| PATCH | `/api/v1/commodities/categories/{category_id}` | `commodities.categories.update` | Bearer token | Working | Update commodity category by public ID. |
| DELETE | `/api/v1/commodities/categories/{category_id}` | `commodities.categories.delete` | Bearer token | Working | Delete commodity category by public ID. |

## Commodity Units

| Method | Path | Permission Code | Auth | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/commodities/units` | `commodities.units.list` | Bearer token | Working | List commodity measurement units. |
| POST | `/api/v1/commodities/units` | `commodities.units.create` | Bearer token | Working | Create commodity unit. |
| GET | `/api/v1/commodities/units/{unit_id}` | `commodities.units.read` | Bearer token | Working | Get commodity unit by public ID. |
| PATCH | `/api/v1/commodities/units/{unit_id}` | `commodities.units.update` | Bearer token | Working | Update commodity unit by public ID. |
| DELETE | `/api/v1/commodities/units/{unit_id}` | `commodities.units.delete` | Bearer token | Working | Delete commodity unit by public ID. |

## Commodities

| Method | Path | Permission Code | Auth | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/commodities` | `commodities.list` | Bearer token | Working | List commodities. |
| POST | `/api/v1/commodities` | `commodities.create` | Bearer token | Working | Create commodity. |
| GET | `/api/v1/commodities/{commodity_id}` | `commodities.read` | Bearer token | Working | Get commodity by public ID. |
| PATCH | `/api/v1/commodities/{commodity_id}` | `commodities.update` | Bearer token | Working | Update commodity by public ID. |
| DELETE | `/api/v1/commodities/{commodity_id}` | `commodities.delete` | Bearer token | Working | Delete commodity by public ID. |

## Markets

| Method | Path | Permission Code | Auth | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/markets` | `markets.list` | Bearer token | Working | List markets. |
| POST | `/api/v1/markets` | `markets.create` | Bearer token | Working | Create market. |
| GET | `/api/v1/markets/{market_id}` | `markets.read` | Bearer token | Working | Get market by public ID. |
| PATCH | `/api/v1/markets/{market_id}` | `markets.update` | Bearer token | Working | Update market by public ID. |
| DELETE | `/api/v1/markets/{market_id}` | `markets.delete` | Bearer token | Working | Soft-delete market by public ID. |

## Market Prices

| Method | Path | Permission Code | Auth | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/market-prices` | `market_prices.list` | Bearer token | Working | List market commodity prices. |
| POST | `/api/v1/market-prices` | `market_prices.create` | Bearer token | Working | Create market commodity price. |
| GET | `/api/v1/market-prices/{price_id}` | `market_prices.read` | Bearer token | Working | Get market commodity price by public ID. |
| PATCH | `/api/v1/market-prices/{price_id}` | `market_prices.update` | Bearer token | Working | Update market commodity price by public ID. |
| DELETE | `/api/v1/market-prices/{price_id}` | `market_prices.delete` | Bearer token | Working | Soft-delete market commodity price by public ID. |
| GET | `/api/v1/markets/{market_id}/prices` | `market_prices.list` | Bearer token | Working | List prices for a market. |
| POST | `/api/v1/markets/{market_id}/prices` | `market_prices.create` | Bearer token | Working | Create price for a market. |
| GET | `/api/v1/markets/{market_id}/latest-prices` | `market_prices.latest` | Bearer token | Working | Latest price per commodity in a market. |

## Commodity Price Views

| Method | Path | Permission Code | Auth | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/commodities/{commodity_id}/prices` | `commodity_prices.list` | Bearer token | Working | List prices for a commodity across markets. |
| GET | `/api/v1/commodities/{commodity_id}/price-history` | `commodity_prices.history` | Bearer token | Working | View commodity price history. |
| GET | `/api/v1/commodities/{commodity_id}/price-comparison` | `commodity_prices.compare` | Bearer token | Working | Compare commodity prices across markets. |

## Administrative Areas

| Method | Path | Permission Code | Auth | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/areas` | `areas.list` | Bearer token | Working | List administrative areas. |
| POST | `/api/v1/areas` | `areas.create` | Bearer token | Working | Create administrative area. |
| POST | `/api/v1/areas/bulk` | `areas.bulk_import` | Bearer token | Working | Bulk import administrative areas by path. |
| GET | `/api/v1/areas/{area_id}` | `areas.read` | Bearer token | Working | Get administrative area by public ID. |
| PATCH | `/api/v1/areas/{area_id}` | `areas.update` | Bearer token | Working | Update administrative area by public ID. |
| DELETE | `/api/v1/areas/{area_id}` | `areas.delete` | Bearer token | Working | Delete administrative area by public ID. |

## Commodity Listings

| Method | Path | Permission Code | Auth | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/listings` | `listings.list` | Bearer token | Working | List commodity listings. |
| POST | `/api/v1/listings` | `listings.create` | Bearer token | Working | Create commodity listing. |
| GET | `/api/v1/listings/{listing_id}` | `listings.read` | Bearer token | Working | Get commodity listing by public ID. |
| PATCH | `/api/v1/listings/{listing_id}` | `listings.update` | Bearer token | Working | Owner/participant rule. Update commodity listing by public ID. |
| DELETE | `/api/v1/listings/{listing_id}` | `listings.delete` | Bearer token | Working | Owner/participant rule. Delete commodity listing by public ID. |

## Orders

| Method | Path | Permission Code | Auth | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/orders` | `orders.list` | Bearer token | Working | List visible orders. |
| POST | `/api/v1/orders` | `orders.create` | Bearer token | Working | Place an order. |
| GET | `/api/v1/orders/{order_id}` | `orders.read` | Bearer token | Working | Owner/participant rule. Get order by public ID. |
| PATCH | `/api/v1/orders/{order_id}` | `orders.update` | Bearer token | Working | Owner/participant rule. Update order by public ID. |

## API Documentation

| Method | Path | Permission Code | Auth | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/schema` | None | None | Working | OpenAPI schema. |
| GET | `/api/docs` | None | None | Working | Swagger UI documentation. |

## Admin

| Method | Path | Permission Code | Auth | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| GET | `/admin/` | None | Django admin session | Working | Django admin site. |
