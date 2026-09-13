# Architecture Notes

## Current decision
The project starts as a Modular Monolith.

## Core
Identity, Access, Organization, People, Documents, Workflow, Notifications, Search, Audit, Settings, Events.

## Business modules
HR, Customers, Suppliers, Contracts, Tasks, Operations.

## Identity
Person = real human. User = internal system login identity. Authentication credentials belong to User.

Commerce Customer is a separate Virtual Store identity domain and must not be merged into internal Person/User/Employee. Cross-track association uses controlled opaque references/API contracts only; there is no direct Commerce database access from the Super App.

## Organization hierarchy
Holding → Company → Branch / Unit.

## Authentication (B2)
Argon2 password hashing + JWT bearer access token + current-user dependency.

## Authorization (B3)
Decision model:
User + Role + Permission + Organization Scope.

Rules:
1. Deny by default.
2. Authorization is checked server-side on every protected request.
3. JWT proves identity only; roles and permissions are intentionally not embedded in the JWT.
4. Every role assignment is organization-scoped; no implicit cross-company access exists.
5. `SELF` grants only the exact organization.
6. `SELF_AND_DESCENDANTS` grants the organization and descendants only.
7. Disabled/expired access components stop granting access immediately.

## Module rules
1. Business modules must not directly access another module's database tables.
2. Cross-module communication goes through defined application/service interfaces.
3. Accounting is outside this project.
4. New modules must follow a standard module contract.
5. Public API routes are versioned under `/api/v1`.
6. Authentication and authorization remain separate concerns.
7. Management endpoints require explicit B3 permission guards.
8. The Virtual Store is a parallel track. Reuse Super App capabilities through contracts, not shared identity or direct cross-domain table access.
9. Commerce registration/login/cart/checkout/payment/order must remain available independently of internal CRM.
10. Payment card PAN/CVV/PIN/raw credentials are outside application data boundaries and must never be stored/logged by these services.
