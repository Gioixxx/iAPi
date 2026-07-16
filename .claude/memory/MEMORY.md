---
type: memory
tags: [memory, index]
updated: [2026-07-16]
---

# iAPi — FastAPI + Ollama (Raspberry Pi 5)
> Contesto persistente. Aggiornato da /remember. Vault Obsidian: vedi workflows/obsidian-vault.md.

**Stack:** Python 3.12 / FastAPI / httpx / Ollama / Docker (arm64)  **Sprint:** v1 gateway + deploy su Pi  **Aggiornamento:** 2026-07-16

## Contesto
Gateway FastAPI davanti a Ollama, deployato su un Raspberry Pi 5 (CasaOS) via l'MCP `pi-deploy`,
per esporre inferenza IA (`llama3.2:3b`) agli altri container Docker in LAN. Codice applicativo
scaffoldato e testato localmente (pytest + docker build); build/publish GHCR e deploy reale sul
Pi ancora da eseguire (richiedono credenziali/conferma dell'utente). Vedi [[decisions]] per il
dettaglio delle scelte architetturali.

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
