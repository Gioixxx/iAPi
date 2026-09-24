---
type: sprint
tags: [memory, sprint]
updated: [2026-07-16]
---

# Sprint Corrente
Stato lavoro in corso. Aggiornato con /sprint. Backlog in [[backlog]], debito in [[tech-debt]].

## Sprint attivo
- **Nome/Numero:** v0.2 — provider LM Studio sul Pi
- **Periodo:** 2026-09-24 →
- **Obiettivo:** modello piccolo che risponda veloce a email e testi brevi, servito da LM Studio
  (llmster) sull'host del Pi, con Ollama come fallback.

## Task
- [x] Provider `lmstudio` accanto a `ollama` (`LLM_PROVIDER`), campo `system` su `/generate`,
  verificato contro LM Studio reale in locale — commit `08a31b7`
- [x] Script `deploy/lmstudio/install-llmster.sh` + README con la sequenza di deploy
- [x] llmster sul Pi: installato, gemma-4-e2b scaricato (Pi da 8 GB). Due fallimenti da
  ETXTBSY risolti con un retry (`3c82f34`) — vedi [[decisions]]
- [x] Unit `lmstudio.service` installata e attiva (enabled, riparte al boot), gateway `ready`
- [x] Build + push `ghcr.io/gioixxx/iapi:0.2.0`/`:latest`
- [x] `deploy_app` con `LLM_PROVIDER=lmstudio`: `/health` ready, email in 6-7 s a caldo
- [x] Interfaccia web su `GET /` (`a250deb`) + log di raggiungibilità: immagine `0.3.0`
  pubblicata e in esecuzione sul Pi (digest `8bf48f85`). Email con le istruzioni della pagina:
  ~22 s alla prima richiesta con istruzioni nuove, ~8,5 s dopo (cache del prompt di LM Studio)
- [x] gemma-4-e2b rispetta `reasoning_effort: none` (0 reasoning token)
- [x] Streaming: `/generate/stream` (NDJSON) + interfaccia che mostra il testo mentre arriva —
  `8c87bc6`, immagine `0.4.0` sul Pi (digest `7f5d6f86`). Prima parola in 0,9 s, email intera
  ~8,7 s. Verificato che chiudere la connessione ferma la generazione su LM Studio (CPU del Pi
  da ~80% a riposo subito dopo la chiusura)

## Storico
### v1 — Gateway FastAPI + Ollama su Raspberry Pi 5
- **Periodo:** 2026-07-16 → 2026-07-16
- **Obiettivo:** gateway custom davanti a Ollama (`llama3.2:3b`) deployato sul Pi 5, così altri
  container Docker in LAN possono fare inferenza — **completato**.
- Task:
  - [x] Gateway FastAPI (`app/`): client Ollama isolato, bootstrap/pull modello in background,
    endpoint `/generate` + `/health`
  - [x] Test pytest (respx-mocked, 8/8 verdi) + lint ruff pulito
  - [x] Dockerfile multi-stage arm64-ready, sanity check build locale
  - [x] `deploy/` (docker-compose + .env.example) per `pi-deploy`
  - [x] Primo commit + push su `github.com/Gioixxx/iAPi`
  - [x] Build arm64 + push `ghcr.io/gioixxx/iapi:0.1.0`/`:latest` (pubblico)
  - [x] Deploy sul Pi (`deploy_app`, Watchtower auto-generato)
  - [x] Verifica end-to-end: `/health` ready, `/generate` risponde, testato da container su
    host Docker diverso dal Pi, Ollama non esposto direttamente, restart senza re-pull
- **Note:** dettagli architetturali in [[decisions]], stato deploy live in
  `C:\Users\Gioix\.claude\projects\C--Dev-iAPi\memory\iapi-v1-deployed.md`.
