#!/usr/bin/env bash
# Installa LM Studio headless (llmster) sull'host del Raspberry Pi e lo registra come servizio
# systemd per iAPi. Il server ascolta SOLO sull'IP del bridge docker0: i container del Pi lo
# raggiungono via host.docker.internal (extra_hosts: host-gateway nel compose), la LAN no.
# In headless LM Studio non permette di creare token API (solo dalla GUI), quindi l'isolamento
# passa dal bind, non dall'autenticazione.
#
# Da eseguire sul Pi come utente normale, non root (sudo serve solo per la unit systemd).
# Idempotente: rieseguirlo riscrive la unit e riavvia il servizio.
#
# Override opzionali: LMSTUDIO_MODEL, LMSTUDIO_PORT, LMSTUDIO_CONTEXT_LENGTH, LMSTUDIO_BIND_IP.
set -euo pipefail

MODEL="${LMSTUDIO_MODEL:-google/gemma-4-e2b}"
PORT="${LMSTUDIO_PORT:-1234}"
# Un'email sta abbondantemente in 8k token (prompt max 8000 caratteri + max_tokens 4096 di iAPi);
# un contesto più ampio costa solo RAM per la KV cache.
CONTEXT_LENGTH="${LMSTUDIO_CONTEXT_LENGTH:-8192}"
LMS="$HOME/.lmstudio/bin/lms"
UNIT=/etc/systemd/system/lmstudio.service
RUN_AS="$(id -un)"

if [ "$(id -u)" -eq 0 ]; then
  echo "Eseguire come utente normale, non come root: llmster vive in \$HOME/.lmstudio." >&2
  exit 1
fi
if [ "$(uname -m)" != aarch64 ]; then
  echo "Atteso aarch64 (Raspberry Pi 5), trovato $(uname -m)." >&2
  exit 1
fi

mem_gb=$(awk '/MemTotal/ {printf "%d", $2 / 1024 / 1024}' /proc/meminfo)
echo "RAM totale: ${mem_gb} GB"
if [ "$mem_gb" -lt 7 ]; then
  echo "ATTENZIONE: meno di 8 GB di RAM — $MODEL e il container Ollama insieme potrebbero" \
    "non starci." >&2
fi

BIND_IP="${LMSTUDIO_BIND_IP:-$(ip -4 -o addr show docker0 2>/dev/null | awk '{print $4}' | cut -d/ -f1)}"
if [ -z "$BIND_IP" ]; then
  echo "IP di docker0 non trovato: Docker è installato e attivo?" >&2
  exit 1
fi
echo "Bind del server: $BIND_IP:$PORT"

# L'installer di LM Studio cerca ldconfig nel PATH, ma su Debian sta in /usr/sbin, che non è
# nel PATH di un utente normale: senza questo si ferma con "ldconfig must be available".
export PATH="$PATH:/usr/sbin:/sbin"

if [ ! -x "$LMS" ]; then
  echo "== Installazione di LM Studio (llmster)"
  curl -fsSL https://lmstudio.ai/install.sh | bash
fi
if [ ! -x "$LMS" ]; then
  echo "Installazione completata ma $LMS non esiste: controlla l'output dell'installer." >&2
  exit 1
fi

echo "== Download del modello $MODEL"
"$LMS" daemon up
"$LMS" get "$MODEL" --yes
# Il daemon avviato qui è fuori dal cgroup del servizio: lo si ferma perché sia systemd a
# possederlo, così stop/restart della unit lo gestiscono davvero.
"$LMS" daemon down

echo "== Unit systemd $UNIT"
sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=LM Studio server (llmster) per iAPi
Wants=docker.service network-online.target
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=$RUN_AS
Environment="HOME=$HOME"
ExecStartPre=$LMS daemon up
ExecStartPre=$LMS load $MODEL --context-length $CONTEXT_LENGTH --yes
ExecStart=$LMS server start --bind $BIND_IP --port $PORT
ExecStop=$LMS daemon down

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable lmstudio.service
sudo systemctl restart lmstudio.service

echo "== Verifica"
for _ in $(seq 1 30); do
  if curl -fsS -o /dev/null "http://$BIND_IP:$PORT/api/v1/models"; then
    break
  fi
  sleep 2
done
if ! curl -fsS -o /dev/null "http://$BIND_IP:$PORT/api/v1/models"; then
  echo "LM Studio non risponde su $BIND_IP:$PORT. Log del servizio:" >&2
  sudo journalctl -u lmstudio.service -n 30 --no-pager >&2
  exit 1
fi
echo "OK: LM Studio risponde su http://$BIND_IP:$PORT"
"$LMS" ps

# Stessa strada che userà iAPi: da un container sulla rete del compose verso l'IP di docker0.
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx iapi-gateway; then
  if docker exec iapi-gateway python -c \
    "import urllib.request; urllib.request.urlopen('http://$BIND_IP:$PORT/api/v1/models', timeout=5)"; then
    echo "OK: raggiungibile dal container iapi-gateway"
  else
    echo "ATTENZIONE: il container iapi-gateway non raggiunge $BIND_IP:$PORT (firewall?)." >&2
  fi
fi
