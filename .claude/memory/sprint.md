---
type: sprint
tags: [memory, sprint]
updated: [2026-07-16]
---

# Sprint Corrente
Stato lavoro in corso. Aggiornato con /sprint. Backlog in [[backlog]], debito in [[tech-debt]].

## Sprint attivo
- **Nome/Numero:** nessuno — v1 chiuso, in attesa del prossimo obiettivo

## Task
- [ ] [nessun task in corso]

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
