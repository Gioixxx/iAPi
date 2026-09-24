---
type: conventions
tags: [memory, conventions]
updated: [2026-07-16]
---

# Convenzioni Locali
Pattern e regole specifiche del progetto. Workaround che generano debito → [[tech-debt]].

### Layer AI isolato in app/ai/
- **Contesto:** qualunque codice che parla HTTP con un backend IA (Ollama, LM Studio).
- **Regola:** vive solo in `app/ai/` (un `<backend>_client.py` per le chiamate HTTP di ogni
  backend, `services/` per l'orchestrazione) — mai direttamente in `app/api/endpoints/`. Il client non importa nulla di
  FastAPI, resta riusabile fuori da un contesto web.
- **Esempio:** `app/ai/ollama_client.py:OllamaClient`, `app/ai/lmstudio_client.py:LMStudioClient`,
  `app/ai/services/generate_service.py`. Un backend nuovo implementa `LLMClient`
  (`app/ai/base.py`) e traduce i propri errori negli `LLM*Error`: readiness, service ed endpoint
  non devono mai importare un client concreto, solo `base.py` o la factory `app/ai/client.py`.
- **Perché diverge:** deviazione intenzionale dallo stack FastAPI standard di claude-libs
  (che non prevede questo layer) per seguire il pattern "isola il layer AI" di
  `stacks/ai-integration.md` — vedi [[decisions]].

## Sezioni comuni
- **Struttura cartelle:** vedi layout completo in `README.md` e nel piano
  `C:\Users\Gioix\.claude\plans\serene-gathering-peacock.md`; niente `models/`/`db/` (nessuna
  persistenza propria, lo stato vive nel backend IA).
- **Vincoli noti:** vedi [[tech-debt]] per gli scostamenti deliberati (auth, CI/CD, streaming).
