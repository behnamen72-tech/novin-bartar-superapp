# Phase B6.3 — Main Layout & Navigation

B6.3 turns the B6.2 single-page preview into a reusable application shell for the remaining operational UI phases.

## Delivered

### Reusable application shell

The authenticated workspace is now split into dedicated frontend components instead of keeping login, navigation, dashboard, and all Core views in one monolithic `app/page.tsx` file.

New primary components:

- `components/app/AppShell.tsx`
- `components/session/LoginScreen.tsx`
- `components/dashboard/Dashboard.tsx`
- `components/core/CoreViews.tsx`
- `lib/navigation.ts`

`app/page.tsx` now owns session lifecycle, view-data loading, browser history synchronization, and composition of those components.

### Permission-aware navigation

Navigation definitions are centralized in `lib/navigation.ts`.

Visible navigation is derived from the effective permissions already returned by `/api/session/state`:

- Organization: `organization.read` or `organization.manage`
- People: `people.read` or `people.manage`
- Users: `users.read` or `users.manage`
- Access: `access.read` or `access.manage`
- Audit: `audit.read`
- Dashboard: always visible to an authenticated user

This is UX filtering only. It does not grant access. FastAPI/B3 authorization remains authoritative for every backend request.

### Browser navigation state

The active Core view is reflected in the browser URL:

- dashboard: `/`
- example Core view: `/?view=organizations`

Back/Forward navigation is supported via `popstate`. Unknown view values fall back to Dashboard. A known view that is not visible under the user's current effective permissions also falls back to Dashboard and does not trigger the protected data request.

No token, role assignment, or sensitive identifier is encoded into the URL.

### Responsive navigation

Desktop uses the persistent right-side navigation rail. Mobile uses an explicit drawer with:

- open/close controls
- backdrop dismissal
- Escape-key dismissal
- automatic close after navigation
- `aria-current="page"` for the active item
- a skip-to-content link for keyboard users

The previous behavior that simply hid the sidebar on small screens has been removed for the B6.3 shell.

### Workspace context

The header now exposes non-sensitive session context:

- current page breadcrumb
- active-session indicator
- current user identity
- number of organization scopes
- number of effective permissions

The sidebar also shows the number of currently assigned organization scopes.

## Security properties preserved

- Access and refresh tokens remain HttpOnly and are not moved into client-visible storage.
- B6.2 refresh rotation and BFF CSRF controls are unchanged.
- Frontend navigation visibility is never treated as authorization.
- Direct/deep-linked unauthorized views are filtered in the client and remain protected again by backend authorization if a request is attempted through another path.
- Logout remains server-mediated through `/api/session/logout`.

## Verification

See `B6.3_TEST_RESULTS.md`.

B6.3 adds a deterministic navigation check (`npm run check:b63`) covering permission visibility, URL parsing/fallback, and location generation. The repository still requires normal `npm install` before full Next.js `typecheck`, `lint`, and `build` can run.

## Next

B6.4 can build the operational dashboard on this shell without changing authentication/navigation architecture. B6.5+ can then add write-capable Organization, People, User, Access, and Document screens incrementally.
