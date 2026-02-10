The pydantic skill files have been created. Here's a summary of what was generated:

**3 files created in `.claude/skills/pydantic/`:**

1. **SKILL.md** (~80 lines) - Quick reference with:
   - Domain model, request DTO, and str enum examples from this codebase
   - Key conventions table (IDs, timestamps, extra="ignore", enums, optionals)
   - Model categories table mapping to file locations
   - Cross-references to fastapi, python, stripe, and twilio skills

2. **references/patterns.md** (~140 lines) - Deep patterns including:
   - `generate_id`/`utc_now` factory functions and why `default_factory` is required
   - `ConfigDict(extra="ignore")` pattern with MongoDB `_id` defense-in-depth
   - `(str, Enum)` dual inheritance and `.value` usage in MongoDB ops
   - Partial update DTO pattern with `None` filtering
   - Provider interface model conventions
   - 3 WARNING anti-patterns with problem/why/fix structure

3. **references/workflows.md** (~130 lines) - Step-by-step workflows:
   - Adding new domain models (with checklist)
   - Adding enums, request/response DTOs, provider interface models
   - Extending existing models (backwards-compatible field additions)
   - MongoDB hydration workflow (query, check, hydrate, use)
   - WARNING about ISO timestamp conversion for inserts
   - Validation feedback loop at the end