#!/usr/bin/env python3
"""
Ultra JEV Navigator - Standalone Autonomous Runner
Uso:
  python runner.py --url "https://exemplo.com" --goal "Pesquisar cotação de BTC" [--cdp "127.0.0.1:9223"] [--record]
"""
import argparse
import asyncio
import json
import os
import sys
import time
import websockets

# Import local modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from modules.router import DualModelRouter
from modules.dispatcher import dispatch_action, cdp_eval
from modules.screencast import record_screencast, open_test_tab, close_tab

def format_elements_table(elements):
    lines = []
    for el in elements:
        val = f" (value: '{el['value']}')" if el.get("value") else ""
        chk = f" [checked={el['checked']}]" if el.get("type") == "checkbox" else ""
        lines.append(f"[{el['id']}] <{el['tag']}> {el['label']}{val}{chk}")
    return "\n".join(lines)

async def run_task(url, goal, cdp_host="127.0.0.1:9223", record=True, out_dir="output_run"):
    os.makedirs(out_dir, exist_ok=True)
    
    # Load indexer JS
    indexer_path = os.path.join(os.path.dirname(__file__), "..", "modules", "jev_indexer.js")
    with open(indexer_path, "r", encoding="utf-8") as f:
        indexer_code = f.read()

    print(f"[Runner] Abrindo aba em: {url} (CDP: {cdp_host})...")
    tab = open_test_tab(cdp_host, url)
    ws_url = tab.get("webSocketDebuggerUrl")
    tab_id = tab.get("id")

    recorder_task = None
    if record:
        print("[Runner] Gravador de tela ativado...")
        recorder_task = asyncio.create_task(
            record_screencast(ws_url, out_dir, max_seconds=15, fps_limit=8)
        )

    router = DualModelRouter()
    history = []
    success = False

    try:
        async with websockets.connect(ws_url, max_size=25*1024*1024) as ws:
            await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
            await asyncio.sleep(1.0)

            for step in range(1, 8):
                # 1. Indexação JEV
                elements = await cdp_eval(ws, indexer_code)
                if not elements:
                    print(f"[Step {step}] Nenhum elemento interativo encontrado.")
                    await asyncio.sleep(1)
                    continue

                table_str = format_elements_table(elements)
                print(f"\n--- [Passo {step}] Observação ({len(elements)} elementos) ---")
                
                # 2. Decisão do Modelo (Dual Router)
                decision = router.decide(goal, table_str, history)
                if decision.get("status") != "ok":
                    print(f"[Passo {step}] Erro de decisão: {decision}")
                    break

                action_data = decision["action"]
                print(f"[Passo {step}] [{decision['model']}] Ação: {action_data} (latência: {decision['latency']}s)")
                history.append(f"Turn {step}: {json.dumps(action_data)}")

                if action_data.get("action", "").upper() == "DONE":
                    print("[Runner] Modelo sinalizou objetivo concluído!")
                    success = True
                    break

                # 3. Execução
                await dispatch_action(ws, action_data)
                await asyncio.sleep(0.6)

    finally:
        if recorder_task:
            await recorder_task
        close_tab(cdp_host, tab_id)

    print(f"\n[Runner] Execução finalizada! Sucesso: {success}")
    if record:
        print(f"[Runner] Gravação disponível em: {os.path.join(out_dir, 'replay.html')}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ultra JEV Navigator Runner")
    parser.add_argument("--url", required=True, help="URL inicial de navegação")
    parser.add_argument("--goal", required=True, help="Objetivo da tarefa em linguagem natural")
    parser.add_argument("--cdp", default="127.0.0.1:9223", help="Host:Porta do Chrome CDP")
    parser.add_argument("--record", action="store_true", help="Gravar screencast da execução")
    parser.add_argument("--out", default="memory/browser_benchmark/cli_run", help="Diretório de saída")
    args = parser.parse_args()

    asyncio.run(run_task(args.url, args.goal, args.cdp, args.record, args.out))
