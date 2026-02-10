All three files are created. Here's a summary of what was generated:

**`.claude/skills/axios/SKILL.md`** (93 lines) — Quick overview covering:
- Global singleton setup with interceptors in `App.js`
- GET, POST/PATCH patterns with code examples
- Parallel fetches with `Promise.all`
- Error detail extraction
- Key conventions table
- Links to reference files and related skills (react, fastapi, react-hook-form)

**`.claude/skills/axios/references/patterns.md`** (148 lines) — DO/DON'T pairs covering:
- Import and base URL conventions (protected vs public pages)
- GET, POST, PATCH, DELETE request patterns from the actual codebase
- Query parameter construction with `URLSearchParams`
- Parallel requests with `Promise.all`
- Three error handling tiers (toast+detail, console+toast, silent)
- 4 anti-patterns with WARNING headers: custom instances, manual auth headers, `defaults.baseURL`, forgetting to refetch after mutations

**`.claude/skills/axios/references/workflows.md`** (137 lines) — Step-by-step workflows:
- Adding a new page checklist (6 steps) with boilerplate template
- Adding new API calls to existing pages
- Error handling decision tree
- Auth flow diagram (login → interceptor → 401 redirect)
- Anti-pattern: infinite loop with token refresh in interceptors
- Debugging API issues guide

All 17 code blocks use actual patterns from this codebase. Cross-references to **react**, **fastapi**, and **react-hook-form** skills are included where relevant.