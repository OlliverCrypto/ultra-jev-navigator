import asyncio
import json
import os
import sys
import time
import urllib.request
import re
import websockets
from screencast import record_screencast, open_test_tab, close_tab
from test_server import BenchmarkHandler
import socketserver
import threading

CDP_HOST = "127.0.0.1:9223"
SERVER_PORT = 18900
OUTPUT_BASE = r"C:\Users\Olliver_Crypto\.openclaw\workspace\memory\browser_benchmark\phase2"
os.makedirs(OUTPUT_BASE, exist_ok=True)

def start_local_server():
    server = socketserver.TCPServer(("127.0.0.1", SERVER_PORT), BenchmarkHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server

def get_env_keys():
    env_file = r'C:\Users\Olliver_Crypto\.openclaw\workspace\.env'
    keys = {}
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                keys[k.strip()] = v.strip()
    return keys

KEYS = get_env_keys()

def call_llm_decision(provider, model_id, goal, elements_table, history):
    system_prompt = (
        "You are an ultrafast, precise browser automation agent. "
        "You operate on an indexed element table [1], [2]... "
        "Allowed actions:\n"
        "- CLICK: {\"action\": \"CLICK\", \"target\": <id>}\n"
        "- TYPE_TEXT: {\"action\": \"TYPE_TEXT\", \"target\": <id>, \"text\": \"<text>\"}\n"
        "- SELECT: {\"action\": \"SELECT\", \"target\": <id>, \"value\": \"<value>\"}\n"
        "- SCROLL_DOWN: {\"action\": \"SCROLL_DOWN\"}\n"
        "- DONE: {\"action\": \"DONE\"}\n"
        "Return ONLY the raw JSON object. No explanation, no markdown fence."
    )

    user_content = f"GOAL: {goal}\n\nCURRENT OBSERVATION:\n{elements_table}\n"
    if history:
        user_content += f"\nPREVIOUS ACTIONS:\n" + "\n".join(history)
    user_content += "\nWhat is the next single action?"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    if provider == "nvidia":
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        headers["Authorization"] = f"Bearer {KEYS.get('NVIDIA_API_KEY')}"
        body = {
            "model": model_id,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 200
        }
    elif provider == "openrouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers["Authorization"] = f"Bearer {KEYS.get('OPENROUTER_API_KEY')}"
        body = {
            "model": model_id,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 200
        }
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    t0 = time.time()
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elapsed = round(time.time() - t0, 3)
            msg = data["choices"][0]["message"]
            raw_content = msg.get("content") or msg.get("reasoning_content") or ""
            
            # Extract JSON
            match = re.search(r'\{[^{}]*\}', raw_content)
            if match:
                parsed = json.loads(match.group(0))
                return {"status": "ok", "action": parsed, "latency": elapsed, "raw": raw_content}
            return {"status": "parse_error", "raw": raw_content, "latency": elapsed}
    except Exception as e:
        return {"status": "error", "error": str(e), "latency": round(time.time() - t0, 3)}

async def cdp_eval(ws, expr):
    cmd_id = int(time.time() * 1000) % 100000
    msg = {
        "id": cmd_id,
        "method": "Runtime.evaluate",
        "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}
    }
    await ws.send(json.dumps(msg))
    while True:
        resp = await ws.recv()
        data = json.loads(resp)
        if data.get("id") == cmd_id:
            return data.get("result", {}).get("result", {}).get("value")

def format_elements_table(elements):
    lines = []
    for el in elements:
        val = f" (value: '{el['value']}')" if el.get("value") else ""
        chk = f" [checked={el['checked']}]" if el.get("type") == "checkbox" else ""
        lines.append(f"[{el['id']}] <{el['tag']}> {el['label']}{val}{chk}")
    return "\n".join(lines)

async def run_autonomous_scenario(model_info, scenario_name, scenario_url, goal, verification_expr):
    provider, model_id = model_info
    clean_name = f"{provider}_{model_id.replace('/', '_').replace(':', '_')}"
    run_dir = os.path.join(OUTPUT_BASE, f"{clean_name}_{scenario_name}")
    os.makedirs(run_dir, exist_ok=True)

    with open(r"C:\Users\Olliver_Crypto\.openclaw\workspace\scripts\browser_harness\jev_indexer.js", "r", encoding="utf-8") as f:
        indexer_code = f.read()

    tab = open_test_tab(CDP_HOST, scenario_url)
    ws_url = tab.get("webSocketDebuggerUrl")
    tab_id = tab.get("id")

    # Iniciar screencast
    recorder_task = asyncio.create_task(
        record_screencast(ws_url, run_dir, max_seconds=12, fps_limit=8)
    )

    history = []
    total_model_latency = 0
    decision_steps = 0
    success = False
    start_time = time.time()

    async with websockets.connect(ws_url, max_size=25*1024*1024) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
        await asyncio.sleep(0.8)

        max_iterations = 6
        for it in range(max_iterations):
            decision_steps += 1
            # 1. Obter indexação JEV atualizada
            elements = await cdp_eval(ws, indexer_code)
            table_str = format_elements_table(elements)

            # 2. Consultar decisão do LLM
            dec = call_llm_decision(provider, model_id, goal, table_str, history)
            total_model_latency += dec.get("latency", 0)

            if dec.get("status") != "ok":
                print(f"    [Turn {it+1}] Falha de decisão do modelo: {dec}")
                break

            action_data = dec["action"]
            act_type = action_data.get("action", "").upper()
            target_id = action_data.get("target")
            history.append(f"Turn {it+1}: {json.dumps(action_data)}")
            print(f"    [Turn {it+1}] Ação decidida: {action_data} ({dec['latency']}s)")

            if act_type == "DONE":
                break

            # 3. Executar ação no DOM
            if act_type == "CLICK":
                await cdp_eval(ws, f"document.querySelector('[data-jev-id=\"{target_id}\"]')?.click();")
            elif act_type == "TYPE_TEXT":
                txt = action_data.get("text", "")
                await cdp_eval(ws, f"""
                    (() => {{
                        const el = document.querySelector('[data-jev-id="{target_id}"]');
                        if (el) {{
                            el.value = {json.dumps(txt)};
                            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }}
                    }})()
                """)
            elif act_type == "SELECT":
                val = action_data.get("value", "")
                await cdp_eval(ws, f"""
                    (() => {{
                        const el = document.querySelector('[data-jev-id="{target_id}"]');
                        if (el) {{
                            el.value = {json.dumps(val)};
                            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                    }})()
                """)
            elif act_type == "SCROLL_DOWN":
                await cdp_eval(ws, "window.scrollBy(0, 500);")

            await asyncio.sleep(0.5)

            # 4. Checar se a verificação do cenário foi atingida
            verif_res = await cdp_eval(ws, verification_expr)
            if verif_res:
                success = True
                print(f"    [Goal Reached!] Condição de sucesso atendida!")
                break

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
        "avg_latency_per_step": round(total_model_latency / max(decision_steps, 1), 2),
        "steps": decision_steps,
        "history": history,
        "recording_path": os.path.join(run_dir, "recording.webp"),
        "replay_html": os.path.join(run_dir, "replay.html")
    }

async def run_phase2():
    print("==================================================")
    print(" INICIANDO BENCHMARK FASE 2: MODELOS FREE NO JEV")
    print("==================================================")

    server = start_local_server()
    print("[Server] Local benchmark server ativo na porta 18900")

    models_to_test = [
        ("nvidia", "stepfun-ai/step-5-preview"),
        ("openrouter", "deepseek/deepseek-v4.1-flash"),
    ]

    scenarios = [
        (
            "sc1_busca_cotacao",
            f"http://127.0.0.1:{SERVER_PORT}/scenario1",
            "Digite o ticker 'BTC' no campo de busca e clique em Pesquisar",
            "document.getElementById('res-price')?.innerText === '$68,450.00'"
        ),
        (
            "sc2_formulario_ordem",
            f"http://127.0.0.1:{SERVER_PORT}/scenario2",
            "Selecione o par 'BTC-PERP', digite a quantidade '2.5', marque a caixa de confirmacao de risco e clique em Executar Ordem",
            "document.getElementById('order-id')?.innerText === 'ORD-94821'"
        ),
    ]

    matrix_results = []

    for model_info in models_to_test:
        print(f"\n>>> AVALIANDO MODELO: [{model_info[0]}] {model_info[1]}")
        for sc_name, sc_url, goal, verif in scenarios:
            print(f"  * Cenário: {sc_name}")
            res = await run_autonomous_scenario(model_info, sc_name, sc_url, goal, verif)
            matrix_results.append(res)
            print(f"    --> Resultado: {'PASSOU' if res['success'] else 'FALHOU'} em {res['total_elapsed']}s ({res['steps']} passos)")

    out_file = os.path.join(OUTPUT_BASE, "PHASE2_MATRIX_RESULTS.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(matrix_results, f, indent=2)

    print(f"\n==================================================")
    print(f" FASE 2 CONCLUIDA! Relatório gravado em: {out_file}")
    print("==================================================")
    return matrix_results

if __name__ == "__main__":
    asyncio.run(run_phase2())
