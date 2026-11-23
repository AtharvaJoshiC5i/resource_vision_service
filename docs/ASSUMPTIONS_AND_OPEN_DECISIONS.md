# Assumptions and open decisions

Documented defaults for build and test until product owners sign off. See handoff §12.

| ID | Topic | Build default | Status |
|----|--------|---------------|--------|
| D1 | Skill level order | Foundational &lt; Applied &lt; Advanced &lt; Expert; startup fails on unknown | Config |
| D2 | Bench horizon | 3 months ahead for Future Bench | Open |
| D3 | No-record month bookable | Yes at full capacity (176) when HR-matched and employed | Open |
| D4 | Ranking tie-break | Employee key ascending | Open |
| D5 | Interview hold overlap | Allowed; only Reserved/Confirmed reduce bookable hours | Open |
| D6 | Contract eligibility | Flag `contract_eligibility: unimplemented` on candidates | Open |
| D7 | Skill name match | Case-insensitive exact match | Open |
| D8 | PT write path | Stub writer until PT API/SQL sign-off | **Critical — Phase 0** |
| D9 | rv2 refresh | Outbox debounce 30s; call refresh script when wired | Open |
| D11 | KB/MNH contracts | Stub JSON payloads in `contracts/` | Open |
| D12 | Unverifiable identity/skills | Exclude from ranking with reason | Proposal |
| D13 | PT table rebuild | Assume writes may be lost until PT confirms SoR | **Critical — Phase 0** |
| D15 | Embedding | iframe + postMessage (`RV_POOLS_READY`, `RV_POOLS_RESULT`) | Proposal |
| D16 | employee_tagging / row_id | Writer stub stores logical keys only; no row_id as PK | **Open** |
| D17 | ZingHR writes | Intent events to stub only | Open |
| D18 | Staffing DB | PostgreSQL in docker-compose; SQLite for unit tests | Proposal |
| D19 | Commitment rows | Same as dashboard: all PT rows with valid effort count | **Critical — Open** |
| D20 | Confirmed marker | From launch payload `project_status: confirmed` + config list | **Critical — Open** |
| D21 | Window overflow | Refuse with structured error unless `ALLOW_WINDOW_EXTEND=true` | Open |

## Phase 0 actions (Project Track team)

- Confirm system of record and safe write surface for `dbo.project_track_proposals_table`.
- Provide sandbox and at least one confirmed project fixture for integration tests.
- Agree launch token and callback origin for production.