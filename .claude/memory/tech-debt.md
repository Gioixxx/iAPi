---
type: tech-debt
tags: [memory, tech-debt]
updated: [2026-07-16]
---

# Tech Debt
Registro debito tecnico con priorità. Aggiornato da /session-end. Origine spesso in [[conventions]].

### Nessuna autenticazione su /generate e /health
- **Priorità:** Media
- **Area:** app/api (gateway HTTP)
- **Data:** 2026-07-16
- **Descrizione:** chiunque sulla LAN può chiamare il gateway, nessun controllo di accesso.
- **Perché rimandato:** v1 pensato per LAN fidata; slot già cablato (`get_optional_api_key` in
  `app/api/deps.py`) per aggiungerla senza toccare le route — vedi [[decisions]].
- **Impatto:** rischio se il Pi finisse esposto oltre la LAN fidata.
- **Risoluzione:** implementare il body di `get_optional_api_key` (header `X-API-Key`).

### Niente CI/CD, build/push arm64 manuale
- **Priorità:** Bassa
- **Area:** build/release
- **Data:** 2026-07-16
- **Descrizione:** ogni release richiede `docker buildx build --push` a mano dalla macchina dev.
- **Perché rimandato:** scelta deliberata per iterazione rapida su progetto personale — vedi
  [[decisions]].
- **Impatto:** nessun altro può rilasciare, nessuna verifica automatica pre-release.
- **Risoluzione:** GitHub Actions con `docker/build-push-action` multi-arch, se serve in futuro.

### /generate non supporta streaming
- **Priorità:** Bassa
- **Area:** app/api/endpoints/generate.py
- **Data:** 2026-07-16
- **Descrizione:** risposta singola JSON dopo il completamento, niente SSE/NDJSON.
- **Perché rimandato:** i chiamanti attuali sono altri servizi backend (machine-to-machine), non
  serve ancora latenza token-by-token.
- **Impatto:** basso oggi; da rivedere se arriva un consumer chat-UI-style.
- **Risoluzione:** endpoint `/generate/stream` separato, senza toccare quello esistente.

### `--workers 1` hardcoded nel Dockerfile
- **Priorità:** Bassa
- **Area:** Dockerfile / app/core/readiness.py
- **Data:** 2026-07-16
- **Descrizione:** `ModelReadiness` vive in memoria di processo — più worker Uvicorn
  divergerebbero sullo stato di readiness.
- **Perché rimandato:** Ollama sul Pi 5 è comunque il vero collo di bottiglia, non il gateway.
- **Impatto:** limita la concorrenza lato gateway (non lato inferenza).
- **Risoluzione:** condividere readiness fuori processo (es. Redis) se mai servissero più worker.

### Tag `ollama/ollama` pinnato a mano, nessun auto-update
- **Priorità:** Bassa
- **Area:** deploy/docker-compose.yml
- **Data:** 2026-07-16
- **Descrizione:** `OLLAMA_IMAGE_TAG` (attualmente `0.32.0`) va controllato/aggiornato a mano;
  Watchtower traccia solo l'immagine `iapi`, non quella di Ollama.
- **Perché rimandato:** fuori scope per v1, Ollama non cambia spesso.
- **Impatto:** minimo — si nota solo se serve una feature/fix di una versione più recente.
- **Risoluzione:** aggiornare `OLLAMA_IMAGE_TAG` in `deploy/.env` a mano quando serve.

### LM Studio sul Pi va esposto oltre localhost
- **Priorità:** Media
- **Area:** deploy (LM Studio / llmster sull'host)
- **Data:** 2026-09-24
- **Descrizione:** perché il container `iapi` raggiunga llmster sull'host, il server deve
  ascoltare oltre `127.0.0.1`; su `0.0.0.0` è visibile a tutta la LAN, il che rompe il principio
  "solo il gateway è esposto" valido per Ollama.
- **Perché rimandato:** dipende da dove girerà LM Studio (host del Pi o altra macchina), non
  ancora deciso.
- **Impatto:** chiunque in LAN può usare LM Studio direttamente, scavalcando il gateway.
- **Risoluzione:** autenticazione di LM Studio attiva + `LMSTUDIO_API_TOKEN`, oppure bind sul
  solo IP del bridge Docker, oppure `network_mode: host` per `iapi`.

### `reasoning_effort: "none"` non è rispettato da tutti i modelli su `/v1`
- **Priorità:** Bassa
- **Area:** app/ai/lmstudio_client.py
- **Data:** 2026-09-24
- **Descrizione:** bug noti di LM Studio (lmstudio-bug-tracker #988, #2413) su alcuni modelli
  ignorano il campo sull'endpoint OpenAI-compatibile; funziona sulla REST nativa `/api/v1/chat`.
- **Perché rimandato:** verificato funzionante su qwen3-0.6b; gemma-4-e2b non ancora provato.
- **Impatto:** risposte più lente e, con `max_tokens` basso, 502 da reasoning che consuma il budget.
- **Risoluzione:** se succede col modello scelto, passare la generazione a `/api/v1/chat` con
  reasoning off, lasciando invariato il resto del client.

## Priorità
- **Alta:** —
- **Media:** nessuna auth su /generate e /health, LM Studio esposto oltre localhost
- **Bassa:** niente CI/CD, no streaming, `--workers 1`, tag Ollama pinnato a mano,
  `reasoning_effort` ignorato da alcuni modelli

## Archiviato
- [item risolti]
