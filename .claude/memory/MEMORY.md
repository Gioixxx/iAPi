---
type: memory
tags: [memory, index]
updated: [2026-09-24]
---

# iAPi — FastAPI + LLM locale (Raspberry Pi 5)
> Contesto persistente. Aggiornato da /remember. Vault Obsidian: vedi workflows/obsidian-vault.md.

**Stack:** Python 3.12 / FastAPI / httpx / Ollama + LM Studio / Docker (arm64)  **Sprint:** provider LM Studio  **Aggiornamento:** 2026-09-24

## Contesto
Gateway FastAPI davanti a un backend LLM locale, deployato su un Raspberry Pi 5 (CasaOS) via
l'MCP `pi-deploy`, per dare agli altri container Docker in LAN un modello piccolo e veloce
(email, testi brevi). v1 (Ollama, `llama3.2:3b`) live e verificato dal 2026-07-16. Dal
2026-09-24 c'è anche il provider LM Studio (`LLM_PROVIDER=lmstudio`), non ancora deployato: resta
da decidere dove far girare llmster. Vedi [[decisions]] per il dettaglio delle scelte.

## File memoria (carica su richiesta)
> `@file.md` = import Claude · `[[file]]` = wikilink Obsidian (graph). Tieni entrambi.
- @decisions.md — [[decisions]] — scelte tecniche con motivazioni
- @domain.md — [[domain]] — glossario, entità, regole di business
- @sprint.md — [[sprint]] — task correnti e obiettivi
- @conventions.md — [[conventions]] — pattern specifici del progetto
- @tech-debt.md — [[tech-debt]] — debito tecnico con priorità
- @backlog.md — [[backlog]] — funzionalità e idee lungo termine
- @adr.md — [[adr]] — ADR formali

## Segnalibri critici
- [decisioni o vincoli da tenere sempre a mente]
