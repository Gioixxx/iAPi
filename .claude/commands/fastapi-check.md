# /fastapi-check — Verifica convenzioni FastAPI

## Input
File corrente. `@.claude/libs/stacks/fastapi.md`, `snippets/fastapi-patterns.md`, `@.claude/memory/conventions.md`. Context7 per fastapi/py.

## Regole
- Checklist: Router (response_model, status_code, Depends), Schema (model_config, separati input/output, EmailStr), Model (Mapped, index, UUID), Service (async/await, HTTPException), Auth (get_current_user, bcrypt, python-jose)
- ✅/⚠️/❌ per criterio

## Output
Checklist per tipo, punteggio X/Y
