---
triggers: inizio sessione | briefing sessione | session start
---
# /session-start — Briefing sessione

## Input
1. `@.claude/memory/MEMORY.md` (sempre)
2. `@.claude/memory/sprint.md` (sempre, per stato sprint corrente)
3. `decisions.md`, `tech-debt.md` (su richiesta o se citati in MEMORY.md)
4. `git log --oneline -10`, `git status`, `git diff --stat`

## Avvio del provider LLM (prima del sidecar)

Assicurati che il provider locale sia attivo **prima** di usare il sidecar: esegui
`scripts/ensure-llm.ps1` dal clone canonico della libreria
(`~/.claude/claude-libs/scripts/ensure-llm.ps1`; se stai lavorando dentro il repo
claude-libs usa `scripts/ensure-llm.ps1`):

```powershell
powershell -File ~/.claude/claude-libs/scripts/ensure-llm.ps1
```

Lo script risolve il provider attivo (`LLM_PROVIDER` > `models.json` → `llm.provider` >
`ollama`) e delega a `ensure-ollama.ps1` oppure a `setup/setup-lmstudio.ps1`. È idempotente:
se il server è già attivo esce subito (exit 0), altrimenti lo avvia e attende che sia pronto.
È l'unica azione non di sola lettura consentita in `/session-start`. Se restituisce exit != 0
(provider non installato o non avviabile) **non** bloccare il briefing: prosegui senza sidecar.

## Sidecar Ollama

Chiama sempre `summarize_session` con la concatenazione di `git log --oneline -10`, `git status`,
`git diff --stat` ed eventuale ultima entry di `.claude/memory/session-log.md`, prima di
sintetizzare tu stesso: usa `summary` come bozza per "ultimo lavoro" e `open_points`/`next_steps`
come bozza per "dove ripartire" — integra la bozza con MEMORY.md e sprint.md. Salta solo se il
tool non è disponibile in sessione o la risposta segnala `ollama_unavailable: true`: in tal caso
**non** bloccare il briefing — sintetizza direttamente da git log e memoria.

## Regole
- Solo lettura — non modificare (unica eccezione: avvio di Ollama, vedi sopra)
- Sintetizza — leggibile in 30 secondi
- Evidenzia modifiche non committate
- Se memoria vuota, suggerisci `/remember`

## Output
Progetto, ultimo lavoro, stato working tree, sprint, tech debt, dove ripartire
