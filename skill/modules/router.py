import urllib.request
import json
import os
import re
import time

def get_env_keys():
    env_file = r'C:\Users\Olliver_Crypto\.openclaw\workspace\.env'
    keys = {}
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    keys[k.strip()] = v.strip()
    return keys

KEYS = get_env_keys()

class DualModelRouter:
    """
    Roteador inteligente de dois níveis:
    1. Tactical (Tier 1): OpenRouter DeepSeek V4.1 Flash (latência ~0.9s, alta velocidade)
    2. Analytical / Fallback (Tier 2): NVIDIA StepFun Step 5 Preview (latência ~1.8s, reasoning para auto-cura e páginas complexas)
    """
    def __init__(self):
        self.primary_provider = "openrouter"
        self.primary_model = "deepseek/deepseek-v4.1-flash"
        self.analytical_provider = "nvidia"
        self.analytical_model = "stepfun-ai/step-5-preview"

    def decide(self, goal, elements_table, history=None, force_analytical=False):
        provider = self.analytical_provider if force_analytical else self.primary_provider
        model_id = self.analytical_model if force_analytical else self.primary_model

        res = self._call_model(provider, model_id, goal, elements_table, history)
        # Se o modelo tático falhar no parsing ou tiver erro, faz failover automático para o analítico (Step 5)
        if not force_analytical and res.get("status") != "ok":
            print(f"[DualRouter] Fallback ativado -> Recorrendo ao modelo analítico {self.analytical_model}")
            res = self._call_model(self.analytical_provider, self.analytical_model, goal, elements_table, history)
        return res

    def _call_model(self, provider, model_id, goal, elements_table, history):
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
                "max_tokens": 250
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
            raise ValueError(f"Unknown provider: {provider}")

        t0 = time.time()
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                elapsed = round(time.time() - t0, 3)
                msg = data["choices"][0]["message"]
                raw_content = msg.get("content") or msg.get("reasoning_content") or ""
                
                match = re.search(r'\{[^{}]*\}', raw_content)
                if match:
                    parsed = json.loads(match.group(0))
                    return {
                        "status": "ok",
                        "provider": provider,
                        "model": model_id,
                        "action": parsed,
                        "latency": elapsed,
                        "raw": raw_content
                    }
                return {
                    "status": "parse_error",
                    "provider": provider,
                    "model": model_id,
                    "raw": raw_content,
                    "latency": elapsed
                }
        except Exception as e:
            return {
                "status": "error",
                "provider": provider,
                "model": model_id,
                "error": str(e),
                "latency": round(time.time() - t0, 3)
            }
