import urllib.request
import json
import os
import re

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

def call_model(provider, model_id, prompt):
    system_prompt = (
        "You are an ultrafast browser action agent. "
        "Given the indexed element table and goal, decide the next operation. "
        "Allowed operations: CLICK, TYPE_TEXT, DONE, WAIT. "
        "Output JSON only in this exact format:\n"
        '{"action": "CLICK|TYPE_TEXT|DONE|WAIT", "target": <integer_index>, "text": "<text_to_type_if_applicable>"}'
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json"
    }

    if provider == "opencode":
        url = "https://opencode.ai/zen/v1/chat/completions"
        headers["Authorization"] = f"Bearer {KEYS.get('OPENCODE_API_KEY')}"
        body = {
            "model": model_id,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 150
        }
    elif provider == "openrouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers["Authorization"] = f"Bearer {KEYS.get('OPENROUTER_API_KEY')}"
        body = {
            "model": model_id,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 150
        }
    elif provider == "nvidia":
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        headers["Authorization"] = f"Bearer {KEYS.get('NVIDIA_API_KEY')}"
        body = {
            "model": model_id,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 250
        }
    else:
        raise ValueError(f"Unknown provider: {provider}")

    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            msg = data["choices"][0]["message"]
            raw_content = msg.get("content") or ""
            # Fallback for models using reasoning_content when content is null or enclosed
            if not raw_content and msg.get("reasoning_content"):
                raw_content = msg.get("reasoning_content")
            
            # Extract JSON block
            json_match = re.search(r'\{[^{}]*\}', raw_content)
            if json_match:
                parsed = json.loads(json_match.group(0))
                return {"status": "ok", "raw": raw_content, "parsed": parsed}
            return {"status": "parse_error", "raw": raw_content}
    except Exception as e:
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    sample_prompt = """Goal: Buscar o ticker 'BTC' no portal
Indexed Elements:
[1] input [type=text] "Ex: BTC, ETH, SOL, PETR4" (value: "")
[2] button "Pesquisar"

What is the next single action to take?"""

    test_models = [
        ("opencode", "big-pickle"),
        ("opencode", "mimo-v2.6-flash-free"),
        ("openrouter", "deepseek/deepseek-v4.1-flash"),
        ("nvidia", "stepfun-ai/step-5-preview"),
    ]

    print("=== TESTANDO CHAMADAS DE DECISAO NOS 4 MODELOS FREE ===")
    for provider, m_id in test_models:
        print(f"\nTestando: [{provider}] {m_id}...")
        res = call_model(provider, m_id, sample_prompt)
        print(f"Status: {res.get('status')}")
        if res.get("status") == "ok":
            print(f"Parsed Action: {res.get('parsed')}")
        else:
            print(f"Details: {res}")
