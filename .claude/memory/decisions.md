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

### LM Studio affiancato a Ollama, selezione esplicita con `LLM_PROVIDER`
- **Data:** 2026-09-24
- **Decisione:** secondo backend `lmstudio` accanto a `ollama` (default invariato), scelto con
  `LLM_PROVIDER`; nessun auto-detect né fallback a catena. `app/ai/` diviso per provider:
  `base.py` (errori `LLM*`, `GenerationResult`, `LLMClient` Protocol), `ollama_client.py`,
  `lmstudio_client.py`, factory `create_llm_client` in `client.py`. Readiness, service e
  `/health` non conoscono più il provider.
- **Perché:** l'obiettivo è un modello piccolo che risponda veloce (email e testi brevi). Stessa
  scelta già fatta in claude-libs: l'auto-detect renderebbe non deterministico quale modello
  risponde. Il nome del provider resta nei messaggi d'errore per il debug.
- **Alternative:** colibri (JustVugg/colibri) — scartato: solo modelli MoE enormi con streaming
  degli esperti da NVMe, niente modelli densi, nessun binario arm64, una richiesta alla volta.
- **Impatto:** `app/ai/*`, `app/core/{config,readiness}.py`, `app/api/deps.py`,
  `app/schemas/health.py`, `deploy/`. `/health` guadagna `provider`/`llm_reachable`;
  `ollama_reachable` resta come alias deprecato. `/generate` guadagna `system` opzionale.

### LM Studio: `/v1` per generare, REST nativa `/api/v1` per presenza e download
- **Data:** 2026-09-24
- **Decisione:** generazione su `POST /v1/chat/completions`; presenza del modello su
  `GET /api/v1/models` (match su `key` o `variants`); download automatico con
  `POST /api/v1/models/download` + polling di `/api/v1/models/download/status/{job_id}`.
  Richiede LM Studio/llmster >= 0.4.0.
- **Perché:** la superficie OpenAI non ha né download né un elenco affidabile dei modelli
  scaricati (`/v1/models` li elenca solo con il JIT loading attivo). Il download automatico
  mantiene la parità col pull self-healing di Ollama.
- **Verificato sul server reale (LM Studio locale, `qwen3-0.6b`):**
  - `reasoning_effort: "none"` azzera i token di reasoning: risposta email da 5,8 s a 1,6 s → è
    il default di `LMSTUDIO_REASONING_EFFORT`. Con reasoning attivo e `max_tokens` basso
    `content` torna `""` con `finish_reason: "length"` → `LLMEmptyResponseError` → 502 esplicito
    invece di una risposta vuota con 200.
  - Con un solo modello caricato, un `model` inesistente viene servito **in silenzio** dal
    modello caricato (200). Senza modelli caricati: 400 con `error.param == "model"` →
    `LLMModelMissingError`. Download di una chiave inesistente: 404 `model_not_found`.
- **Impatto:** `app/ai/lmstudio_client.py`, `tests/test_lmstudio_client.py`.

### LM Studio fuori dal compose
- **Data:** 2026-09-24
- **Decisione:** il compose non contiene LM Studio; `iapi` lo raggiunge via `LMSTUDIO_BASE_URL`
  (default `http://host.docker.internal:1234`, con `extra_hosts: host-gateway`). Il container
  Ollama resta nel compose come fallback.
- **Perché:** l'immagine ufficiale `lmstudio/llmster-preview` è solo x86 e CPU; l'unica arm64 è
  di terze parti. Installato sull'host del Pi (`install.sh`) o su un'altra macchina in LAN.
- **Impatto:** `deploy/docker-compose.yml`, `deploy/.env.example`.

### llmster sul Pi in ascolto solo su `docker0`, non su `0.0.0.0` con token
- **Data:** 2026-09-24
- **Decisione:** LM Studio gira sull'host del Pi come unit systemd (`lmstudio.service`, creata da
  `deploy/lmstudio/install-llmster.sh`) con `lms server start --bind <IP di docker0>`. Il modello
  è caricato all'avvio (`lms load --context-length 8192`), quindi resta sempre in memoria.
- **Perché:** in headless LM Studio non permette di creare token API (solo dalla GUI), quindi
  "`0.0.0.0` + token" non è praticabile. `host.docker.internal:host-gateway` risolve proprio
  all'IP di `docker0`: i container ci arrivano via INPUT dell'host, la LAN no. Mantiene il
  principio "solo il gateway è esposto" già valido per Ollama.
- **Alternative:** `network_mode: host` per `iapi` — scartata: Ollama non avrebbe più il DNS di
  servizio e andrebbe pubblicato su `127.0.0.1`, cambio più invasivo. Immagine arm64 di terze
  parti nel compose — scartata per la supply chain.
- **Conseguenze note:** la unit ha `After=docker.service` perché `docker0` deve esistere al bind;
  se l'IP di `docker0` cambiasse (es. `bip` in `daemon.json`) va rieseguito lo script. Il Pi non
  è raggiungibile via SSH da Claude Code (solo tramite l'MCP `pi-deploy`, che non esegue comandi
  arbitrari): lo script lo lancia l'utente.
- **Impatto:** `deploy/lmstudio/install-llmster.sh`, `.gitattributes` (`*.sh` in LF).
