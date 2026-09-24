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

- `GET /` — interfaccia web per scrivere email, risposte, messaggi e correzioni: apri
  `http://192.168.1.50:8000/` da qualsiasi dispositivo della LAN, telefono compreso. È servita dal
  gateway stesso perché una pagina ospitata altrove in HTTPS non potrebbe chiamare un indirizzo
  HTTP della LAN. La cronologia resta solo nel browser che la usa.
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
  non sta nel compose: gira sull'host del Pi come servizio systemd, installato da
  `deploy/lmstudio/install-llmster.sh` (vedi [Deploy](#deploy)). Il container `iapi` lo
  raggiunge via `host.docker.internal` (`extra_hosts: host-gateway`), che su Linux risolve
  all'IP del bridge `docker0`.
- **Esposizione:** il server ascolta **solo** sull'IP di `docker0`: i container del Pi lo
  raggiungono, la LAN no. In modalità headless LM Studio non permette di creare token API
  (solo dalla GUI), quindi l'isolamento passa dal bind. `LMSTUDIO_API_TOKEN` serve solo se
  LM Studio gira su un'altra macchina con l'autenticazione attivata dalla GUI.
- **Velocità:** `LMSTUDIO_REASONING_EFFORT=none` (default) spegne il "thinking" dei modelli che
  lo hanno attivo di default, come gemma-4 e qwen3 — misurato 3,6× più veloce su una risposta
  di lunghezza email. Il servizio systemd carica il modello all'avvio e lo tiene in memoria, così
  nessuna richiesta paga il caricamento.
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

$Version = "0.2.0"
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

### Con LM Studio sull'host del Pi

L'ordine conta: il gateway con `LLM_PROVIDER=lmstudio` resta `degraded` finché LM Studio non
risponde.

1. **LM Studio sul Pi** (una volta; rieseguibile). `deploy_app` sincronizza solo i file compose e
   `.env*`, quindi lo script va copiato a mano:

   ```bash
   scp deploy/lmstudio/install-llmster.sh gioixxx@192.168.1.50:~
   ssh -t gioixxx@192.168.1.50 'bash ~/install-llmster.sh'
   ```

   Installa llmster, scarica `google/gemma-4-e2b`, crea la unit `lmstudio.service` (avvio al
   boot, modello caricato con contesto 8192, bind su `docker0`) e verifica che il container
   `iapi-gateway` lo raggiunga. `sudo` chiede la password per la unit.
2. **Immagine** `0.2.0` + `:latest` con il comando della sezione precedente. Watchtower aggiorna
   subito il gateway in esecuzione, che però continua a usare Ollama: la configurazione sul Pi
   non è ancora cambiata.
3. **Configurazione:** `LLM_PROVIDER=lmstudio` in `deploy/.env`, poi
   `deploy_app("iapi", "C:\Dev\iAPi\deploy")`, che porta sul Pi il compose nuovo (`extra_hosts`,
   variabili `LMSTUDIO_*`) e ricrea il container.
4. **Verifica:** `GET /health` → `provider: lmstudio`, `status: ready`; poi una `/generate` con
   `system`. Per tornare a Ollama: `LLM_PROVIDER=ollama` e di nuovo `deploy_app`.
