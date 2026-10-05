"""Demo de ponta a ponta: consulta cross-domain + tolerância a falhas.

1. Abre um listener no stream de eventos (/events) para mostrar o raciocínio
   distribuído em tempo real.
2. Dispara uma consulta que toca os 3 domínios (logistics/finance/hr).
3. Derruba o container mcp-finance (docker compose stop) e repete a mesma
   consulta várias vezes, mostrando a resposta degradando graciosamente
   (retry -> erro -> circuito aberto -> resposta rápida "indisponível").
4. Religa o container (docker compose start) e repete a consulta uma última
   vez, mostrando a recuperação automática (circuito half-open -> closed).

Uso: python scripts/demo.py  (com `docker compose up --build` já rodando)
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ORCHESTRATOR_URL = "http://localhost:8000"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUERY = "Verifique o pedido 103: estoque, pagamento e disponibilidade do responsável."


def listen_events(stop_event: threading.Event) -> None:
    try:
        resp = urllib.request.urlopen(f"{ORCHESTRATOR_URL}/events", timeout=60)
    except Exception as exc:  # orchestrator ainda não está pronto
        print(f"[events] não foi possível conectar ao stream: {exc}")
        return
    for raw_line in resp:
        if stop_event.is_set():
            break
        line = raw_line.decode("utf-8").strip()
        if line.startswith("data:"):
            payload = json.loads(line[len("data:") :].strip())
            print(f"  [evento] {payload['type']:<16} domain={payload.get('domain')} {payload.get('error') or payload.get('reason') or ''}")


def run_query(label: str) -> None:
    body = json.dumps({"text": QUERY}).encode("utf-8")
    req = urllib.request.Request(
        f"{ORCHESTRATOR_URL}/query", data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        elapsed_ms = (time.monotonic() - started) * 1000
        print(f"\n=== {label} ({elapsed_ms:.0f}ms) ===")
        print(data["answer"])
    except Exception as exc:
        print(f"\n=== {label} — FALHOU: {exc} ===")


def docker_compose(*args: str) -> None:
    subprocess.run(["docker", "compose", *args], cwd=PROJECT_ROOT, check=True)


def main() -> None:
    stop_event = threading.Event()
    listener = threading.Thread(target=listen_events, args=(stop_event,), daemon=True)
    listener.start()
    time.sleep(0.5)

    run_query("Consulta 1 (tudo saudável)")

    print("\n>>> Derrubando mcp-finance para simular falha (docker compose stop mcp-finance)...")
    docker_compose("stop", "mcp-finance")
    time.sleep(1)

    for i in range(2, 6):
        run_query(f"Consulta {i} (mcp-finance fora do ar)")
        time.sleep(1)

    print("\n>>> Religando mcp-finance (docker compose start mcp-finance)...")
    docker_compose("start", "mcp-finance")

    # Aguarda passar do CIRCUIT_RECOVERY_TIMEOUT_S (padrão 15s) para o circuito
    # ir de OPEN para HALF_OPEN e permitir uma nova tentativa de conexão.
    print(">>> Aguardando o circuit breaker entrar em half-open (~16s)...")
    time.sleep(16)

    run_query("Consulta final (mcp-finance recuperado)")

    stop_event.set()


if __name__ == "__main__":
    main()
