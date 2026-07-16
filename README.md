# iAPi

Gateway HTTP davanti a [Ollama](https://ollama.com) che serve un modello IA da 3B parametri
(default `llama3.2:3b`) su un Raspberry Pi 5, cosi che altri container Docker in LAN possano
fare richieste di inferenza senza parlare direttamente con Ollama.

## Endpoint

- `GET /health` — stato del gateway e di Ollama. `200` finche il gateway e vivo e Ollama e
  raggiungibile (anche durante il pull del modello, vedi `status`/`pull_progress_percent` nel
  body); `503` solo se Ollama e davvero irraggiungibile.
- `POST /generate` — `{"prompt": "...", "temperature"?: float, "max_tokens"?: int}` →
  `{"response": "...", "model": "...", "eval_count"?: int, "total_duration_ms"?: int}`.
  Ritorna `503` finche il modello non e stato ancora scaricato, `504` su timeout upstream,
  `502` per altri errori Ollama.

Il pull del modello e automatico al primo avvio del gateway (background task, non blocca lo
startup) e si auto-ripete se il modello dovesse sparire (es. volume resettato) — nessuno step
manuale SSH richiesto.

## Run locale

```bash
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Richiede un Ollama raggiungibile su `OLLAMA_BASE_URL` (default `http://ollama:11434` — per un
run locale senza Docker Compose, punta a `http://localhost:11434` con `ollama serve` in corso).

## Test

```bash
pytest
```

I test mockano `OllamaClient` via `respx` — non serve un Ollama reale.

## Variabili d'ambiente

| Var | Default | Descrizione |
|-----|---------|-------------|
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Base URL del server Ollama |
| `OLLAMA_MODEL` | `llama3.2:3b` | Modello servito |
| `OLLAMA_REQUEST_TIMEOUT_SECONDS` | `120` | Timeout per una singola `/generate` |
| `OLLAMA_PULL_TIMEOUT_SECONDS` | `1800` | Timeout per il pull iniziale del modello |
| `OLLAMA_CONNECT_TIMEOUT_SECONDS` | `5` | Timeout di connessione a Ollama |
| `PULL_RETRY_BACKOFF_SECONDS` | `30` | Backoff tra retry di pull/connessione falliti |
| `READINESS_RECHECK_SECONDS` | `60` | Intervallo di ricontrollo presenza modello dopo `ready` |
| `MAX_PROMPT_CHARS` | `8000` | Limite lunghezza prompt |
| `LOG_LEVEL` | `INFO` | Livello di log |

## Build & publish (arm64 → GHCR)

```powershell
docker buildx create --name iapi-builder --use
docker buildx inspect --bootstrap
docker login ghcr.io -u gioixxx

$Version = "0.1.0"
docker buildx build `
  --platform linux/arm64 `
  --tag "ghcr.io/gioixxx/iapi:$Version" `
  --tag "ghcr.io/gioixxx/iapi:latest" `
  --push .
```

Il package GHCR va reso pubblico dopo il primo push (il Pi non ha credenziali registry) —
vedi impostazioni del package su GitHub.

## Deploy

Vedi `deploy/docker-compose.yml` e `deploy/.env.example`. Deploy tramite l'MCP `pi-deploy`:

```
deploy_app("iapi", "C:\Dev\iAPi\deploy", enable_watchtower=True)
```

Watchtower (auto-generato al primo deploy) rileva i nuovi push su `:latest` e aggiorna i
container senza bisogno di un redeploy manuale.
