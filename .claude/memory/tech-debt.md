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

## Priorità
- **Alta:** —
- **Media:** nessuna auth su /generate e /health
- **Bassa:** niente CI/CD, no streaming, `--workers 1`, tag Ollama pinnato a mano

## Archiviato
- [item risolti]
- **2026-09-24 — LM Studio sul Pi esposto oltre localhost.** Risolto prima del deploy:
  llmster ascolta solo sull'IP di `docker0` (vedi [[decisions]]); il token API non è
  creabile in headless, quindi non era un'opzione.
- **2026-09-24 — `reasoning_effort: "none"` forse ignorato su `/v1`.** Verificato sul Pi con
  gemma-4-e2b: 0 reasoning token. Se si cambia modello va ricontrollato (bug LM Studio #988, #2413).
