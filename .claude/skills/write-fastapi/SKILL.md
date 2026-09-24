---
name: write-fastapi
description: Writes production FastAPI Python code matching claude-libs conventions. Use when creating or editing routers, Pydantic schemas, SQLAlchemy models, services, dependencies, or Python files in a FastAPI project.
---
# Write FastAPI code

Wrapper procedurale. Non copiare le regole qui: leggi i moduli.

## Prima di scrivere

1. Segui `precise-code`.
2. Read `.claude/libs/stacks/fastapi.md` — sezione **Obbligatorie**.
3. Read `.claude/libs/snippets/fastapi-patterns.md` — Router, Schema, SQLAlchemy.
4. Leggi 1–2 file `.py` nello stesso package.
5. Serve un esempio completo → Read `.claude/libs/stacks/fastapi-reference.md` (solo allora).

## Checklist (puntatori, non duplicati)

Applica le **Obbligatorie** del modulo stack: `async def`, Pydantic v2, logica in `services/`, `Depends()`, Alembic, `response_model` su ogni endpoint.
