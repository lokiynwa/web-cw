# Student Affordability Intelligence API - Reference

Concise reference for major endpoints, auth rules, and common errors.

## Base
- Base URL: `/api/v1`

## Authentication
- Public read routes: health + analytics are open.
- Primary website auth: bearer token from account login.
  - `Authorization: Bearer <token>`
- Legacy auth (optional): `X-API-Key: <key>` remains available for admin/dev/MCP scenarios.

Common auth responses:
- `401 Unauthorized`: missing/invalid token or key
- `403 Forbidden`: authenticated but insufficient permissions

## Health
### `GET /health`
- Purpose: liveness check.
- Response: `{ status, timestamp }`

## Account Auth
### `POST /auth/register`
- Purpose: create USER account.
- Body: `email`, `password`, `display_name`
- Notes: duplicate email rejected, password policy enforced.

### `POST /auth/login`
- Purpose: authenticate user account.
- Body: `email`, `password`
- Response: bearer token payload (`access_token`, `token_type`, `expires_in_seconds`).

### `GET /auth/me`
- Purpose: return authenticated user profile.
- Auth: bearer token.

## Submissions
### `GET /submissions`
- Purpose: list submissions.

### `GET /submissions/{submission_id}`
- Purpose: fetch one submission.
- Errors: `404` not found.

### `POST /submissions`
- Purpose: create crowd submission (live immediately).
- Auth: logged-in user (primary) or contributor API key (legacy).
- Body fields:
  - `city` (string)
  - `area` (string, optional)
  - `submission_type` (`PINT` or `TAKEAWAY`)
  - `amount_gbp` (decimal > 0)
  - `venue_name` (optional)
  - `item_name` (optional)
  - `submission_notes` (optional)
- Lifecycle:
  - new rows default to `ACTIVE`
  - `ACTIVE` rows are included in analytics immediately
- Protection logic:
  - plausibility checks (type-specific)
  - duplicate detection in recent window
- Errors:
  - `409` duplicate detected
  - `422` validation/plausibility failure

### `PUT /submissions/{submission_id}`
- Purpose: update submission.
- Auth: owner or moderator.
- Rule: updates only while status is `ACTIVE`.
- Errors: `403`, `404`, `409`, `422`.

### `DELETE /submissions/{submission_id}`
- Purpose: delete submission.
- Auth: owner or moderator.
- Success: `204`.

Ownership notes:
- Normal users can update/delete only their own submissions.
- Moderators can update/delete any submission.

## Moderation (Post-Publication)
### `POST /submissions/{submission_id}/moderation`
- Purpose: apply moderation action.
- Auth: moderator role or moderator API key.
- Body:
  - `moderation_status` (`ACTIVE`, `FLAGGED`, `REMOVED`)
  - `moderator_note` (optional)
- Supported transitions:
  - `ACTIVE -> FLAGGED`
  - `ACTIVE -> REMOVED`
  - `FLAGGED -> ACTIVE`
  - `FLAGGED -> REMOVED`
  - `REMOVED -> ACTIVE`
- Analytics rule:
  - only `ACTIVE` submissions are included.

### `GET /submissions/{submission_id}/moderation`
- Purpose: moderation history/audit trail.
- Auth: moderator.

### `GET /moderation/submissions`
- Purpose: moderation list by status.
- Auth: moderator.
- Query:
  - `moderation_status` (default `ACTIVE`)

## Rental Analytics (Public)
### `GET /analytics/rent/cities/{city}`
- Query filters:
  - `bedrooms` (int)
  - `property_type` (string)
  - `ensuite_proxy` (bool)
- Returns: average, median, min, max, sample size.

### `GET /analytics/rent/cities/{city}/areas/{area}`
- Same filters and metrics as city endpoint.

### `GET /analytics/rent/cities/{city}/areas`
- Purpose: per-area metrics for a city.

## Crowd Cost Analytics (Public)
Only includes `ACTIVE` submissions.

### `GET /analytics/costs/cities/{city}`
- Query:
  - `submission_type` (`PINT` or `TAKEAWAY`, optional)
- Returns: average, median, min, max, sample size.

### `GET /analytics/costs/cities/{city}/areas/{area}`
- Same filter and metrics as city endpoint.

## Affordability (Public)
Transparent bounded scoring using selected components (`rent`, `pint`, `takeaway`).

### `GET /affordability/cities/{city}/score`
- Query:
  - `components` (comma-separated; default all)
  - `rent_weight`, `pint_weight`, `takeaway_weight` (optional, non-negative)
- Returns:
  - `score` (0-100)
  - `score_band`
  - component breakdowns + formula metadata

### `GET /affordability/cities/{city}/areas`
- Same query options as city score.
- Returns per-area scores + breakdowns.

## Key Error Codes
- `400` malformed request payload/query
- `401` missing/invalid auth credentials
- `403` insufficient role/ownership permissions
- `404` missing city/area/submission resource
- `409` duplicate or invalid state transition
- `422` validation or business-rule failure
- `500` missing server-side lookup config (rare)
