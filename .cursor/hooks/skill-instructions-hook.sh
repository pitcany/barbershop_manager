#!/bin/bash
# UserPromptSubmit hook for skill-aware responses

cat <<'EOF'
REQUIRED: SKILL LOADING PROTOCOL

Before writing any code, complete these steps in order:

1. SCAN each skill below and decide: LOAD or SKIP (with brief reason)
   - react
   - fastapi
   - mongodb
   - tailwind
   - frontend-design
   - stripe
   - twilio
   - sendgrid
   - react-hook-form
   - recharts
   - shadcn-ui
   - python
   - pydantic
   - jwt
   - axios

2. For every skill marked LOAD → immediately invoke Skill(name)
   If none need loading → write "Proceeding without skills"

3. Only after step 2 completes may you begin coding.

IMPORTANT: Skipping step 2 invalidates step 1. Always call Skill() for relevant items.

Sample output:
- react: LOAD - building components
- fastapi: SKIP - not needed for this task
- mongodb: LOAD - building components
- tailwind: SKIP - not needed for this task

Then call:
> Skill(react)
> Skill(mongodb)

Now implementation can begin.
EOF
