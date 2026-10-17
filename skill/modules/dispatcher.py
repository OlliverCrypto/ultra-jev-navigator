import json
import asyncio
import random

async def cdp_eval(ws, expression):
    cmd_id = random.randint(10000, 99999)
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

async def dispatch_action(ws, action_data):
    """
    Executa a ação semântica no DOM sobre o elemento indexado [data-jev-id="target"].
    Dispara eventos de input/change e clicks com bubbling nativo para compatibilidade com frameworks (React, Vue, etc.).
    """
    act = action_data.get("action", "").upper()
    target_id = action_data.get("target")

    # Delays humanos leves anti-detecção (LabsClaw stealth)
    await asyncio.sleep(random.uniform(0.1, 0.25))

    if act == "CLICK":
        js = f"""
        (() => {{
            const el = document.querySelector('[data-jev-id="{target_id}"]');
            if (!el) return false;
            el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            el.focus();
            el.click();
            return true;
        }})()
        """
        return await cdp_eval(ws, js)

    elif act == "TYPE_TEXT":
        txt = action_data.get("text", "")
        js = f"""
        (() => {{
            const el = document.querySelector('[data-jev-id="{target_id}"]');
            if (!el) return false;
            el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            el.focus();
            el.value = {json.dumps(txt)};
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return true;
        }})()
        """
        return await cdp_eval(ws, js)

    elif act == "SELECT":
        val = action_data.get("value", "")
        js = f"""
        (() => {{
            const el = document.querySelector('[data-jev-id="{target_id}"]');
            if (!el) return false;
            el.focus();
            el.value = {json.dumps(val)};
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            return true;
        }})()
        """
        return await cdp_eval(ws, js)

    elif act == "SCROLL_DOWN":
        return await cdp_eval(ws, "window.scrollBy({ top: 500, behavior: 'smooth' }); true;")

    elif act == "SCROLL_UP":
        return await cdp_eval(ws, "window.scrollBy({ top: -500, behavior: 'smooth' }); true;")

    elif act in ("DONE", "WAIT"):
        return True

    return False
