# Student Affordability Intelligence API - Reference

Concise reference for major endpoints, request parameters, authentication rules, and common error codes.

## Base
- Base URL: `/api/v1`
- Auth header (protected routes): `X-API-Key: <key>`

## Authentication Rules
- Public read routes: health and analytics routes are open.
- Contributor-protected routes: submission write routes require an API key with contributor permissions.
- Moderator-protected routes: moderation routes require an API key with moderator permissions.

Common auth responses:
- `401 Unauthorized`: missing/invalid API key
- `403 Forbidden`: valid key but insufficient role

## Health
### `GET /health`
- Purpose: liveness check.
- Response: `{ status, timestamp }`

## Submissions
### `GET /submissions`
- Purpose: list submissions.

### `GET /submissions/{submission_id}`
- Purpose: fetch one submission.
- Errors: `404` not found.

### `POST /submissions` (Contributor)
- Purpose: create submission (defaults to `PENDING` moderation).
- Body fields:
  - `city` (string)
  - `area` (string, optional)
  - `submission_type` (`PINT` or `TAKEAWAY`)
  - `amount_gbp` (decimal > 0)
  - `venue_name` (optional)
  - `item_name` (optional)
  - `submission_notes` (optional)
- Protection logic:
  - plausibility checks (type-specific)
  - duplicate detection in recent window
- Errors:
  - `409` duplicate detected
  - `422` validation/plausibility failure

### `PUT /submissions/{submission_id}` (Contributor)
- Purpose: update existing submission.
- Rule: updates only while status is `PENDING`.
- Errors: `404`, `409`, `422`.

### `DELETE /submissions/{submission_id}` (Contributor)
- Purpose: delete submission.
- Success: `204`.

## Moderation
### `POST /submissions/{submission_id}/moderation` (Moderator)
- Purpose: apply moderation decision.
- Body:
  - `moderation_status` (`PENDING`, `APPROVED`, `REJECTED`)
  - `moderator_note` (optional)
- Side effect:
  - `APPROVED` => analytics-eligible
  - `PENDING`/`REJECTED` => not analytics-eligible

### `GET /submissions/{submission_id}/moderation` (Moderator)
- Purpose: moderation history/audit trail.

### `GET /moderation/submissions` (Moderator)
- Purpose: moderation queue listing.
- Query:
  - `moderation_status` (default `PENDING`)

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
Only includes `APPROVED` + analytics-eligible submissions.

### `GET /analytics/costs/cities/{city}`
- Query:
  - `submission_type` (`PINT` or `TAKEAWAY`, optional)
- Returns: average, median, min, max, sample size.

### `GET /analytics/costs/cities/{city}/areas/{area}`
- Same filter and metrics as city endpoint.

## Affordability (Public)
Transparent bounded scoring using selected components (`rent`, `pint`, `takeaway`).
No merged single “cost” component.

### `GET /affordability/cities/{city}/score`
- Query:
  - `components` (comma-separated; default all)
  - `rent_weight`, `pint_weight`, `takeaway_weight` (optional, non-negative)
- Returns:
  - overall `score` (0-100)
  - `score_band`
  - component breakdowns with source metrics and component scores
  - requested vs effective weights
  - formula metadata

### `GET /affordability/cities/{city}/areas`
- Same query options as city score.
- Returns per-area scores + breakdowns.

## Key Error Codes
- `400` malformed request payload/query
- `401` missing/invalid API key
- `403` insufficient role permissions
- `404` missing city/area/submission resource
- `409` duplicate/conflict (for submissions)
- `422` validation or business-rule failure
- `500` missing server-side lookup config (rare)
