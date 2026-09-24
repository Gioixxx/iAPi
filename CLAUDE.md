# iAPi

## Librerie e moduli attivi

<!-- claude-libs:modules:start (auto-generato — modifiche qui vengono rimosse al reconcile; aggiungi i moduli a workspace.json) -->
@.claude/libs/CLAUDE.md
@.claude/libs/stacks/fastapi.md
@.claude/libs/snippets/fastapi-patterns.md
@.claude/libs/stacks/docker.md
@.claude/libs/stacks/ai-integration.md
@.claude/memory/MEMORY.md
<!-- claude-libs:modules:end -->

## Cos'è iAPi

Gateway FastAPI davanti a Ollama, deployato su un Raspberry Pi 5 (CasaOS) via l'MCP
`pi-deploy`. Espone `POST /generate` e `GET /health` così altri container Docker in LAN
possono fare inferenza su un modello 3B (`llama3.2:3b` di default) senza parlare
direttamente con Ollama. Dettagli architetturali completi in `.claude/memory/decisions.md`
e nel piano `C:\Users\Gioix\.claude\plans\serene-gathering-peacock.md`.

Build/test locali: `pytest` (tramite `.venv`), `docker build .`. Build/publish arm64 e
deploy: vedi `README.md`.
