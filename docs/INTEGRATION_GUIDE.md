# Project Track ↔ Resource Vision Pools integration

## Overview

Project Track (separate app) opens **Resource Vision Pools** when the lead clicks **Select employee** on a **confirmed** project. In production, pools may run in an iframe or route hosted by staffing services; the local simulator uses one React app (modal, no iframe). Cross-origin integration still uses **postMessage** and the launch payload documented below.

## URLs (local dev)

| App | URL |
|-----|-----|
| Staffing API | `http://127.0.0.1:8010` |
| Local PT + Pools UI (single app) | `http://127.0.0.1:5175` |

## Launch flow

1. PT builds a launch payload (see `contracts/launch-schema.json`).
2. PT opens iframe: `POOLS_URL?launch=<base64url-json>` or sends `RV_POOLS_INIT` via postMessage after load.
3. Popup validates `launch_token` with staffing API (`IdentityPort`).
4. User completes staffing; popup sends `RV_POOLS_RESULT` to `callback_origin`.

### postMessage protocol

**Parent → iframe (optional after load):**

```json
{ "type": "RV_POOLS_INIT", "payload": { /* launch-schema */ } }
```

**Iframe → parent:**

```json
{ "type": "RV_POOLS_READY" }
```

```json
{
  "type": "RV_POOLS_RESULT",
  "payload": { /* result-schema */ }
}
```

## Authentication

Pass `launch_token` in the launch payload. Dev stub accepts `dev-simulator-token`. Production: replace `IdentityPort` with JWT validation agreed with PT (issuer, audience, project scope).

## Staffing API

OpenAPI: `contracts/openapi-staffing.yaml`. Base path `/api/staffing`.

### Concurrent resource blocks (max 3 leads per employee)

When a lead selects an employee (`POST /api/staffing/candidates`), staffing records an **active block** tied to:

| Field | Source today | Project Track handoff |
|-------|----------------|------------------------|
| `ActorId` | `IdentityPort.resolve(launch_token)["user_id"]` | PT user / lead id (stable) |
| `ActorDisplayName` | `display_name` from the same resolve call | PT display name |

- At most **`EMPLOYEE_BLOCK_MAX`** (default **3**) active blocks per employee across all projects.
- `POST /api/staffing/pools/search` returns `active_blocks`, `block_slots_*`, and `can_block` so the UI can show who already holds the employee and disable selection when full.
- **Reject**, **release**, or **interview expiry** releases one block; **final-check confirm** marks the winning block **Consumed** and releases the other active blocks on that employee.
- HTTP **409** on create when full: `{ "reason": "employee_block_limit", "active_blocks": [...] }`.

Replace `IdentityPort` only; block table columns stay the same.

### Pools search (`POST /api/staffing/pools/search`)

The popup calls this on load (and when filters change). The request carries inherited Project Track row filters, `month_hours`, typed `required_skills`, plus optional `search`, `availability_filter` (`all` | `any` | `every`), and `skill_match_filter` (`all` | `full` | `some`). The response returns ranked employees with skill ticks, bench class, and per-month `status` / `bookable_hours` columns for the project window. See [`DATA_SOURCES.md`](./DATA_SOURCES.md) for upstream systems.

## Events (Project Track → staffing)

`POST /api/staffing/events/project-track` with webhook body documented in OpenAPI. Simulator includes buttons that call this endpoint.

## CORS

Configure `CORS_ORIGINS` on staffing API to include PT and simulator origins.