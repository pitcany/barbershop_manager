All files have been generated. Here's a summary of what was created:

**`.claude/skills/mongodb/`**

| File | Lines | Content |
|------|-------|---------|
| `SKILL.md` | ~110 | Quick overview, conventions table, common patterns, warnings |
| `references/patterns.md` | ~140 | Query patterns, aggregation pipelines, update operators, N+1 warning, shop isolation |
| `references/types.md` | ~130 | Document schemas, Pydantic integration, enum storage, timestamp format, collection schemas table |
| `references/modules.md` | ~140 | DB connection, collection access, agent operations, audit/revenue logging, SMS compliance, scheduled jobs |
| `references/errors.md` | ~140 | Runtime errors, 4 silent failure warnings, missing indexes warning with fix, error handling patterns, troubleshooting checklist |

**Key highlights:**
- **18 code blocks** across all files (exceeds the 15 minimum)
- **5 WARNING anti-patterns** with problem/why/fix structure (enum `.value`, missing `shop_id`, unchecked `modified_count`, unbounded `to_list`, missing indexes)
- All examples sourced from the actual codebase (`server.py`, `agents.py`, `audit.py`, `sms_compliance.py`, `scheduled_jobs.py`)
- Cross-references to **pydantic**, **fastapi**, and **python** skills
- Troubleshooting checklist and validation workflow included
- `allowed-tools` trimmed to only relevant tools (no Stripe/Playwright/etc.)