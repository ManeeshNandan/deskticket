# DeskTicket API

Base URL:

```text
https://YOUR-DESKTICKET-DOMAIN/api/v1/
```

## Authentication

DeskTicket uses JWT authentication.

### Obtain token

```http
POST /api/v1/token/
Content-Type: application/json
```

```json
{
  "username": "demo",
  "password": "Demo@12345"
}
```

Response contains an access and refresh token.

Send the access token on API requests:

```http
Authorization: Bearer <access-token>
```

### Refresh token

```http
POST /api/v1/token/refresh/
Content-Type: application/json
```

```json
{
  "refresh": "<refresh-token>"
}
```

## Tickets

```text
GET    /api/v1/tickets/
POST   /api/v1/tickets/
GET    /api/v1/tickets/{id}/
PUT    /api/v1/tickets/{id}/
PATCH  /api/v1/tickets/{id}/
DELETE /api/v1/tickets/{id}/
```

Search:

```text
GET /api/v1/tickets/?search=login
```

Filters:

```text
GET /api/v1/tickets/?status=OPEN
GET /api/v1/tickets/?priority=HIGH
```

### Reply to a ticket

```http
POST /api/v1/tickets/{id}/reply/
Content-Type: application/json
Authorization: Bearer <access-token>
```

```json
{
  "body": "Thanks for contacting support. We are looking into this request."
}
```

In public demo mode this creates a simulated outbound message and does not send real email.

### Assign a ticket

```http
POST /api/v1/tickets/{id}/assign/
Content-Type: application/json
Authorization: Bearer <access-token>
```

```json
{
  "user_id": 1
}
```

## Departments

```text
GET    /api/v1/departments/
POST   /api/v1/departments/
GET    /api/v1/departments/{id}/
PATCH  /api/v1/departments/{id}/
DELETE /api/v1/departments/{id}/
```

## Categories

```text
GET    /api/v1/categories/
POST   /api/v1/categories/
GET    /api/v1/categories/{id}/
PATCH  /api/v1/categories/{id}/
DELETE /api/v1/categories/{id}/
```

## Customers

```text
GET    /api/v1/customers/
POST   /api/v1/customers/
GET    /api/v1/customers/{id}/
PATCH  /api/v1/customers/{id}/
DELETE /api/v1/customers/{id}/
```

## Notifications

```text
GET   /api/v1/notifications/
PATCH /api/v1/notifications/{id}/
POST  /api/v1/notifications/{id}/read/
```

## Demo environment

Use only synthetic data. Do not send real mailbox credentials, production customer information, or secrets to the public demo.
