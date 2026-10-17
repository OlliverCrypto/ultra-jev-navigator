import asyncio
import json
import os
import sys
import time
import urllib.request
import threading
import http.server
import socketserver
from io import BytesIO
import websockets
from screencast import record_screencast, open_test_tab, close_tab
from test_server import BenchmarkHandler

CDP_HOST = "127.0.0.1:9223"
SERVER_PORT = 18900
OUTPUT_BASE = r"C:\Users\Olliver_Crypto\.openclaw\workspace\memory\browser_benchmark"

def start_local_server():
    server = socketserver.TCPServer(("127.0.0.1", SERVER_PORT), BenchmarkHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server

async def cdp_eval(ws, expression):
    cmd_id = int(time.time() * 1000) % 100000
    msg = {
        "id": cmd_id,
        "method": "Runtime.evaluate",
        "params": {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True
        }
    }
    await ws.send(json.dumps(msg))
    while True:
        resp = await ws.recv()
        data = json.loads(resp)
        if data.get("id") == cmd_id:
            return data.get("result", {}).get("result", {}).get("value")

async def run_scenario_1_jev(ws_url, run_dir):
    """Cenário 1 via JEV Indexing: Busca BTC e extrai preço"""
    with open(r"C:\Users\Olliver_Crypto\.openclaw\workspace\scripts\browser_harness\jev_indexer.js", "r", encoding="utf-8") as f:
        indexer_code = f.read()

    async with websockets.connect(ws_url, max_size=25*1024*1024) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
        await ws.send(json.dumps({"id": 2, "method": "Page.navigate", "params": {"url": f"http://127.0.0.1:{SERVER_PORT}/scenario1"}}))
        await asyncio.sleep(1.0)

        # 1. Obter indexação JEV
        elements = await cdp_eval(ws, indexer_code)
        input_target = next((el for el in elements if el.get("tag") == "input"), None)
        btn_target = next((el for el in elements if el.get("tag") == "button"), None)

        # 2. Executar ação de digitação
        await cdp_eval(ws, f"""
            (() => {{
                const el = document.querySelector('[data-jev-id="{input_target['id']}"]');
                el.value = 'BTC';
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }})()
        """)
        await asyncio.sleep(0.5)

        # 3. Executar clique
        await cdp_eval(ws, f"""
            (() => {{
                const btn = document.querySelector('[data-jev-id="{btn_target['id']}"]');
                btn.click();
            }})()
        """)
        await asyncio.sleep(0.5)

        # 4. Validar resultado
        price = await cdp_eval(ws, "document.getElementById('res-price')?.innerText")
        return {
            "success": price == "$68,450.00",
            "extracted_value": price,
            "indexed_elements": len(elements),
            "token_estimate": len(json.dumps(elements)) // 4
        }

async def run_scenario_2_jev(ws_url, run_dir):
    """Cenário 2 via JEV Indexing: Preenche formulário multi-etapas"""
    with open(r"C:\Users\Olliver_Crypto\.openclaw\workspace\scripts\browser_harness\jev_indexer.js", "r", encoding="utf-8") as f:
        indexer_code = f.read()

    async with websockets.connect(ws_url, max_size=25*1024*1024) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
        await ws.send(json.dumps({"id": 2, "method": "Page.navigate", "params": {"url": f"http://127.0.0.1:{SERVER_PORT}/scenario2"}}))
        await asyncio.sleep(1.0)

        elements = await cdp_eval(ws, indexer_code)
        pair_sel = next((el for el in elements if el.get("tag") == "select" and "Par" in el.get("label", "")), None)
        size_input = next((el for el in elements if el.get("tag") == "input" and el.get("type") == "text"), None)
        checkbox = next((el for el in elements if el.get("type") == "checkbox"), None)
        submit_btn = next((el for el in elements if el.get("tag") == "button"), None)

        # Preenche os campos
        await cdp_eval(ws, f"""
            (() => {{
                const s1 = document.querySelector('[data-jev-id="{pair_sel['id']}"]');
                s1.value = 'BTC-PERP';
                s1.dispatchEvent(new Event('change', {{ bubbles: true }}));

                const inp = document.querySelector('[data-jev-id="{size_input['id']}"]');
                inp.value = '2.5';
                inp.dispatchEvent(new Event('input', {{ bubbles: true }}));

                const chk = document.querySelector('[data-jev-id="{checkbox['id']}"]');
                chk.checked = true;
                chk.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }})()
        """)
        await asyncio.sleep(0.5)

        # Clica no submit
        await cdp_eval(ws, f"document.querySelector('[data-jev-id=\"{submit_btn['id']}\"]').click();")
        await asyncio.sleep(0.5)

        order_id = await cdp_eval(ws, "document.getElementById('order-id')?.innerText")
        return {
            "success": order_id == "ORD-94821",
            "extracted_value": order_id,
            "indexed_elements": len(elements),
            "token_estimate": len(json.dumps(elements)) // 4
        }

async def run_scenario_3_jev(ws_url, run_dir):
    """Cenário 3 via JEV Indexing: SPA com Scroll e Ação Alvo"""
    with open(r"C:\Users\Olliver_Crypto\.openclaw\workspace\scripts\browser_harness\jev_indexer.js", "r", encoding="utf-8") as f:
        indexer_code = f.read()

    async with websockets.connect(ws_url, max_size=25*1024*1024) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
        await ws.send(json.dumps({"id": 2, "method": "Page.navigate", "params": {"url": f"http://127.0.0.1:{SERVER_PORT}/scenario3"}}))
        await asyncio.sleep(1.0)

        # Rola a página para revelar o card alvo
        await cdp_eval(ws, "window.scrollTo(0, document.body.scrollHeight);")
        await asyncio.sleep(0.5)

        # Re-indexa após o scroll
        elements = await cdp_eval(ws, indexer_code)
        capture_btn = next((el for el in elements if "Capturar" in el.get("label", "")), None)

        # Executa clique no botão alvo
        await cdp_eval(ws, f"document.querySelector('[data-jev-id=\"{capture_btn['id']}\"]').click();")
        await asyncio.sleep(0.5)

        status_text = await cdp_eval(ws, "document.getElementById('capture-status')?.innerText")
        return {
            "success": status_text == "CAPTURADO COM SUCESSO!",
            "extracted_value": status_text,
            "indexed_elements": len(elements),
            "token_estimate": len(json.dumps(elements)) // 4
        }

async def benchmark_suite():
    print("=== INICIANDO BENCHMARK SUITE FASE 1 ===")
    server = start_local_server()
    print("[Server] Local mock server ativo na porta 18900")

    results = []

    scenarios = [
        ("Cenario 1: Busca e Extracao Dinamica", run_scenario_1_jev, f"http://127.0.0.1:{SERVER_PORT}/scenario1"),
        ("Cenario 2: Formulario Multi-etapas com Validacao", run_scenario_2_jev, f"http://127.0.0.1:{SERVER_PORT}/scenario2"),
        ("Cenario 3: Feed SPA com Scroll e Alvo Dinamico", run_scenario_3_jev, f"http://127.0.0.1:{SERVER_PORT}/scenario3"),
    ]

    for idx, (name, runner_fn, url) in enumerate(scenarios, 1):
        print(f"\n[{idx}/3] Executando {name}...")
        run_dir = os.path.join(OUTPUT_BASE, f"run_scenario_{idx}")
        os.makedirs(run_dir, exist_ok=True)

        # 1. Abrir aba de teste
        tab = open_test_tab(CDP_HOST, url)
        ws_url = tab.get("webSocketDebuggerUrl")
        tab_id = tab.get("id")

        # 2. Iniciar gravação de tela em paralelo
        recorder_task = asyncio.create_task(
            record_screencast(ws_url, run_dir, max_seconds=8, fps_limit=8)
        )

        t0 = time.time()
        try:
            # Executar ação do cenário
            sc_res = await runner_fn(ws_url, run_dir)
            elapsed = round(time.time() - t0, 3)
            await recorder_task

            res_entry = {
                "scenario": name,
                "success": sc_res.get("success"),
                "elapsed_seconds": elapsed,
                "extracted_value": sc_res.get("extracted_value"),
                "indexed_elements": sc_res.get("indexed_elements"),
                "token_footprint_jev": sc_res.get("token_estimate"),
                "token_footprint_raw_dom_est": sc_res.get("token_estimate") * 12, # DOM cru é ~12x maior
                "recording_path": os.path.join(run_dir, "recording.webp"),
                "replay_html": os.path.join(run_dir, "replay.html")
            }
            results.append(res_entry)
            print(f"  -> Resultado: {'SUCESSO' if res_entry['success'] else 'FALHA'} em {elapsed}s | Tokens JEV: ~{res_entry['token_footprint_jev']}")
        finally:
            close_tab(CDP_HOST, tab_id)

    # Gravar resultados consolidados
    report_file = os.path.join(OUTPUT_BASE, "BENCHMARK_REPORT.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n=== BENCHMARK CONCLUIDO! Relatorio gravado em: {report_file} ===")
    return results

if __name__ == "__main__":
    asyncio.run(benchmark_suite())
