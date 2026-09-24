# iAPi

Gateway HTTP che serve un modello IA piccolo su un Raspberry Pi 5, così che altri container
Docker in LAN possano fare richieste di inferenza (scrittura di email, testi brevi) senza
parlare direttamente con il backend. Il backend si sceglie con `LLM_PROVIDER`:

- `ollama` (default) — container [Ollama](https://ollama.com) nello stesso compose, modello
  `llama3.2:3b`;
- `lmstudio` — server [LM Studio](https://lmstudio.ai) / llmster (>= 0.4.0) esterno al compose,
  modello `google/gemma-4-e2b`, via API compatibile OpenAI.

La scelta è esplicita, mai automatica: con entrambi i server attivi, quale modello risponde non
deve dipendere da quale dei due ha risposto per primo.

## Endpoint

- `GET /health` — stato del gateway e del backend. `200` finché il gateway è vivo e il backend
  è raggiungibile (anche durante il download del modello, vedi `status`/`pull_progress_percent`
  nel body); `503` solo se il backend è davvero irraggiungibile. Il body riporta `provider`,
  `model` e `llm_reachable`; `ollama_reachable` resta come alias deprecato di `llm_reachable`
  per i chiamanti della 0.1.
- `POST /generate` — `{"prompt": "...", "system"?: "...", "temperature"?: float,
  "max_tokens"?: int}` → `{"response": "...", "model": "...", "eval_count"?: int,
  "total_duration_ms"?: int}`. `system` è l'istruzione di ruolo (es. "Scrivi email brevi e
  cortesi in italiano."). Ritorna `503` finché il modello non è stato ancora scaricato, `504` su
  timeout upstream, `502` per gli altri errori del backend — incluso il caso in cui un modello
  "reasoning" consuma tutto `max_tokens` a ragionare senza scrivere la risposta.

Il download del modello è automatico al primo avvio del gateway (background task, non blocca lo
startup) e si ripete da solo se il modello dovesse sparire (es. volume resettato) — con Ollama
via `/api/pull`, con LM Studio via `/api/v1/models/download`. Nessuno step manuale via SSH.

## LM Studio

- **Dove gira:** non esiste un'immagine Docker ufficiale arm64 di llmster, quindi LM Studio
  non sta nel compose. Può girare sull'host del Pi (`curl -fsSL https://lmstudio.ai/install.sh |
  bash`, poi `lms daemon up` e `lms server start`) oppure su un'altra macchina della LAN;
  `LMSTUDIO_BASE_URL` punta a lui. Il container `iapi` risolve `host.docker.internal` all'host
  anche su Linux (`extra_hosts: host-gateway`).
- **Esposizione:** perché il container lo raggiunga, il server deve ascoltare oltre `localhost`.
  Se ascolta su `0.0.0.0` è visibile a tutta la LAN: abilita l'autenticazione in LM Studio e
  imposta lo stesso token in `LMSTUDIO_API_TOKEN`.
- **Velocità:** `LMSTUDIO_REASONING_EFFORT=none` (default) spegne il "thinking" dei modelli che
  lo hanno attivo di default, come gemma-4 e qwen3 — misurato 3,6× più veloce su una risposta
  di lunghezza email. Il primo `/generate` dopo un periodo di inattività include il caricamento
  del modello in memoria (JIT di LM Studio); le richieste successive no.
- **Modello sostituito:** se è caricato un solo modello, LM Studio risponde con quello anche
  quando la richiesta ne nomina un altro. Il gateway blocca `/generate` finché il modello
  configurato non risulta scaricato, e il campo `model` della risposta riporta sempre quello
  che ha davvero risposto (con un warning nel log se differisce).

## Run locale

```bash
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Richiede un backend raggiungibile. Con Ollama: `OLLAMA_BASE_URL=http://localhost:11434` e
`ollama serve` in corso. Con LM Studio: `LLM_PROVIDER=lmstudio` e
`LMSTUDIO_BASE_URL=http://localhost:1234`.

## Test

```bash
pytest
```

I test mockano entrambi i client via `respx` — non serve né un Ollama né un LM Studio reale.

## Variabili d'ambiente

| Var | Default | Descrizione |
|-----|---------|-------------|
| `LLM_PROVIDER` | `ollama` | Backend: `ollama` o `lmstudio` |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Base URL del server Ollama |
| `OLLAMA_MODEL` | `llama3.2:3b` | Modello servito da Ollama |
| `LMSTUDIO_BASE_URL` | `http://host.docker.internal:1234` | Base URL del server LM Studio |
| `LMSTUDIO_MODEL` | `google/gemma-4-e2b` | Chiave del catalogo LM Studio del modello servito |
| `LMSTUDIO_API_TOKEN` | — | Token Bearer, se l'autenticazione di LM Studio è attiva |
| `LMSTUDIO_REASONING_EFFORT` | `none` | `reasoning_effort` inviato a LM Studio; vuoto = non inviato |
| `OLLAMA_REQUEST_TIMEOUT_SECONDS` | `120` | Timeout per una singola `/generate` (entrambi i provider) |
| `OLLAMA_PULL_TIMEOUT_SECONDS` | `1800` | Timeout per il download del modello (entrambi i provider) |
| `OLLAMA_CONNECT_TIMEOUT_SECONDS` | `5` | Timeout di connessione al backend (entrambi i provider) |
| `PULL_RETRY_BACKOFF_SECONDS` | `30` | Backoff tra retry di download/connessione falliti |
| `READINESS_RECHECK_SECONDS` | `60` | Intervallo di ricontrollo presenza modello dopo `ready` |
| `MAX_PROMPT_CHARS` | `8000` | Limite di lunghezza di `prompt` e `system` |
| `LOG_LEVEL` | `INFO` | Livello di log |

I timeout mantengono il prefisso storico `OLLAMA_` per non rompere i deploy esistenti, ma valgono
per entrambi i provider.

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
container senza bisogno di un redeploy manuale. Il container Ollama resta nel compose anche con
`LLM_PROVIDER=lmstudio`: è il fallback, e tornare indietro è solo un cambio di variabile.
