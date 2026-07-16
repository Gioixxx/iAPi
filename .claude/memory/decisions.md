---
type: decisions
tags: [memory, architecture]
updated: [2026-07-16]
---

# Decisioni Architetturali
Registro scelte tecniche con motivazioni.

### Gateway FastAPI davanti a Ollama, non Ollama esposto direttamente
- **Data:** 2026-07-16
- **Decisione:** iAPi è un container FastAPI proprio (non solo config di deploy) che parla con
  un container `ollama/ollama` ufficiale via rete Docker interna, esponendo `POST /generate` e
  `GET /health` come unica API vista dai chiamanti esterni. Ollama non ha porte pubblicate.
- **Perché:** disaccoppia gli altri container in LAN dai dettagli dell'API Ollama, centralizza
  readiness/health (incluso "il modello è già stato scaricato?") e lascia uno slot pronto per
  auth futura senza toccare i chiamanti.
- **Alternative:** esporre Ollama direttamente (`ollama/ollama` + porta pubblicata, zero codice
  custom) — scartata perché l'utente ha chiesto esplicitamente "creare un applicativo" e perché
  centralizzare readiness/auth in un solo posto vale la complessità aggiuntiva minima.
- **Impatto:** `app/ai/client.py`, `app/core/readiness.py`, `deploy/docker-compose.yml`.

### Pull del modello in background nel gateway, non init-container
- **Data:** 2026-07-16
- **Decisione:** il pull del modello (`OLLAMA_MODEL`, default `llama3.2:3b`) avviene come task
  asyncio in background avviato dal lifespan di FastAPI (`app/core/readiness.py:bootstrap_model`),
  non come init-container Compose che blocca l'avvio.
- **Perché:** l'MCP `pi-deploy` (`C:\Users\Gioix\.claude\claude-libs\mcp\pi-deploy\server.py`)
  esegue `docker compose up -d` via SSH con un timeout hardcoded di 60s — un init-container che
  blocca finché un pull di ~2GB non finisce farebbe fallire (in apparenza) ogni deploy. Il
  bootstrap in background ritorna il controllo a Uvicorn in pochi secondi ed è self-healing (si
  ri-pulla da solo se il volume del modello viene resettato, senza step SSH manuali).
- **Alternative:** init-container one-shot con `service_completed_successfully` — scartata per il
  timeout di `deploy_app`; pull sincrono al primo `/generate` — scartata perché renderebbe la
  prima richiesta di ogni chiamante lentissima e imprevedibile.
- **Impatto:** `app/core/readiness.py`, `app/main.py` (lifespan), `deploy/docker-compose.yml`.

### Build arm64 via buildx locale, niente CI/CD in v1
- **Data:** 2026-07-16
- **Decisione:** l'immagine del gateway è buildata da Windows con
  `docker buildx build --platform linux/arm64 --push` verso `ghcr.io/gioixxx/iapi` (tag semver +
  `:latest`), senza GitHub Actions.
- **Perché:** `repo-release`'s `publish_docker` fa solo `docker build` sull'architettura host
  (nessun supporto multi-platform) — inadatto per un target ARM64 da un dev machine x64. GitHub
  Actions sarebbe più "corretto" per la convenzione già documentata in pi-deploy
  ("l'immagine arriva dalla CI/CD"), ma per un progetto personale a iterazione rapida l'utente ha
  preferito buildx locale: nessuna infrastruttura aggiuntiva da mantenere.
- **Alternative:** GitHub Actions con `docker/build-push-action` multi-arch — rimandata, non
  scartata: può essere aggiunta in seguito senza cambiare il Dockerfile.
- **Impatto:** `README.md` (workflow build/publish), nessun `.github/workflows/`.
