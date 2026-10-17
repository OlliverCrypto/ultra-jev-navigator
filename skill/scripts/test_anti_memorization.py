import asyncio
import json
import os
import sys
import time
import urllib.request
import re
import socketserver
import threading
import websockets

# Import skill modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from modules.screencast import record_screencast, open_test_tab, close_tab
from modules.dispatcher import dispatch_action, cdp_eval
from modules.router import DualModelRouter
from scripts.test_server_randomized import AntiMemoHandler

CDP_HOST = "127.0.0.1:9223"
RANDOM_PORT = 18901
OUTPUT_BASE = r"C:\Users\Olliver_Crypto\.openclaw\workspace\memory\browser_benchmark\anti_memorization"
os.makedirs(OUTPUT_BASE, exist_ok=True)

def start_random_server():
    server = socketserver.TCPServer(("127.0.0.1", RANDOM_PORT), AntiMemoHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server

def format_elements_table(elements):
    lines = []
    for el in elements:
        val = f" (value: '{el['value']}')" if el.get("value") else ""
        chk = f" [checked={el['checked']}]" if el.get("type") == "checkbox" else ""
        lines.append(f"[{el['id']}] <{el['tag']}> {el['label']}{val}{chk}")
    return "\n".join(lines)

async def run_anti_memorization_trial(model_info, scenario_num, scenario_name, goal, verif_expr):
    provider, model_id = model_info
    clean_m = f"{provider}_{model_id.replace('/', '_').replace(':', '_')}"
    run_dir = os.path.join(OUTPUT_BASE, f"{clean_m}_{scenario_name}")
    os.makedirs(run_dir, exist_ok=True)

    indexer_path = os.path.join(os.path.dirname(__file__), "..", "modules", "jev_indexer.js")
    with open(indexer_path, "r", encoding="utf-8") as f:
        indexer_code = f.read()

    url = f"http://127.0.0.1:{RANDOM_PORT}/scenario{scenario_num}"
    tab = open_test_tab(CDP_HOST, url)
    ws_url = tab.get("webSocketDebuggerUrl")
    tab_id = tab.get("id")

    # Iniciar screencast
    recorder_task = asyncio.create_task(
        record_screencast(ws_url, run_dir, max_seconds=15, fps_limit=8)
    )

    router = DualModelRouter()
    # Override router to force specific model
    router.primary_provider = provider
    router.primary_model = model_id
    router.analytical_provider = provider
    router.analytical_model = model_id

    history = []
    success = False
    decision_steps = 0
    total_model_latency = 0
    start_time = time.time()
    observed_indices_used = []

    try:
        async with websockets.connect(ws_url, max_size=25*1024*1024) as ws:
            await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
            await asyncio.sleep(0.8)

            for step in range(1, 8):
                decision_steps += 1
                elements = await cdp_eval(ws, indexer_code)
                table_str = format_elements_table(elements)

                print(f"\n      [Passo {step}] Observados {len(elements)} elementos:")
                for el in elements:
                    print(f"        [{el['id']}] <{el['tag']}> {el['label'][:40]}")

                dec = router.decide(goal, table_str, history, force_analytical=True)
                total_model_latency += dec.get("latency", 0)

                if dec.get("status") != "ok":
                    print(f"      [Erro de decisão]: {dec}")
                    break

                action_data = dec["action"]
                act_type = action_data.get("action", "").upper()
                target_id = action_data.get("target")
                if target_id is not None:
                    observed_indices_used.append(target_id)

                print(f"      [Decisão]: {action_data} (latência: {dec['latency']}s)")
                history.append(f"Turn {step}: {json.dumps(action_data)}")

                if act_type == "DONE":
                    break

                # Despachar ação
                await dispatch_action(ws, action_data)
                await asyncio.sleep(0.6)

                # Verificar se o critério foi cumprido
                verif = await cdp_eval(ws, verif_expr)
                if verif:
                    success = True
                    print(f"      >>> SUCESSO! Condição atendida sem decorar posições!")
                    break

    finally:
        await recorder_task
        close_tab(CDP_HOST, tab_id)

    total_elapsed = round(time.time() - start_time, 2)
    return {
        "provider": provider,
        "model": model_id,
        "scenario": scenario_name,
        "success": success,
        "total_elapsed": total_elapsed,
        "total_model_latency": round(total_model_latency, 2),
        "steps": decision_steps,
        "indices_used": observed_indices_used,
        "history": history,
        "recording_path": os.path.join(run_dir, "recording.webp"),
        "replay_html": os.path.join(run_dir, "replay.html")
    }

async def run_anti_memorization_suite():
    print("==================================================================")
    print(" SUITE DE TESTES ANTI-MEMORIZAÇÃO (LAYOUT EMBARALHADO + DECOYS) ")
    print("==================================================================")
    server = start_random_server()
    print(f"[Server] Servidor randomizado ativo na porta {RANDOM_PORT}")

    models = [
        ("nvidia", "stepfun-ai/step-5-preview"),
        ("openrouter", "deepseek/deepseek-v4.1-flash")
    ]

    scenarios = [
        (
            1,
            "sc1_busca_shuffled_with_decoys",
            "Digite o ticker 'BTC' no campo de localizar cotação de ativo cripto e clique em Consultar Ativo",
            "document.getElementById('res-price')?.innerText === '$68,450.00'"
        ),
        (
            2,
            "sc2_formulario_shuffled_with_decoys",
            "Selecione o Par de Negociação 'BTC-PERP', digite a Quantidade de Contratos '2.5', marque a caixa 'Confirmo o dimensionamento de risco' e clique no botão para Enviar Ordem",
            "document.getElementById('order-id')?.innerText === 'ORD-94821'"
        )
    ]

    results = []
    for model_info in models:
        print(f"\n\n>>> TESTANDO: [{model_info[0]}] {model_info[1]}")
        for sc_num, sc_name, goal, verif in scenarios:
            print(f"\n  * Cenário {sc_num}: {sc_name}")
            trial_res = await run_anti_memorization_trial(model_info, sc_num, sc_name, goal, verif)
            results.append(trial_res)
            print(f"    --> Resultado: {'PASSOU (100% DINÂMICO)' if trial_res['success'] else 'FALHOU'} | Tempo: {trial_res['total_elapsed']}s | Índices acionados: {trial_res['indices_used']}")

    report_path = os.path.join(OUTPUT_BASE, "ANTI_MEMORIZATION_REPORT.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n==================================================================")
    print(f" SUITE CONCLUÍDA COM SUCESSO! Relatório: {report_path}")
    print("==================================================================")
    return results

if __name__ == "__main__":
    asyncio.run(run_anti_memorization_suite())
