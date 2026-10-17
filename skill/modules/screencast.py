import asyncio
import json
import os
import sys
import time
import base64
import urllib.request
from io import BytesIO
from PIL import Image
import websockets

def open_test_tab(cdp_host="127.0.0.1:9223", initial_url="about:blank"):
    url = f"http://{cdp_host}/json/new?{initial_url}"
    req = urllib.request.Request(url, method="PUT")
    with urllib.request.urlopen(req, timeout=5) as r:
        tab = json.loads(r.read().decode("utf-8"))
        return tab

def close_tab(cdp_host="127.0.0.1:9223", target_id=""):
    url = f"http://{cdp_host}/json/close/{target_id}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.read().decode("utf-8")
    except Exception as e:
        return str(e)

def get_tab(cdp_host="127.0.0.1:9223", target_id=None):
    url = f"http://{cdp_host}/json/list"
    with urllib.request.urlopen(url, timeout=5) as r:
        tabs = json.loads(r.read().decode("utf-8"))
        if target_id:
            for t in tabs:
                if t.get("id") == target_id:
                    return t
        for t in tabs:
            if t.get("type") == "page":
                return t
        return None

async def record_screencast(ws_url, output_dir, max_seconds=10, fps_limit=10):
    os.makedirs(output_dir, exist_ok=True)
    frames_dir = os.path.join(output_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    print(f"[Recorder] Conectando ao WebSocket: {ws_url}")
    frame_count = 0
    start_time = time.time()
    last_frame_time = 0
    frame_meta = []

    async with websockets.connect(ws_url, max_size=25*1024*1024) as ws:
        # 1. Habilitar Page
        await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
        await ws.send(json.dumps({"id": 2, "method": "Network.enable"}))

        # 2. Iniciar Screencast
        screencast_cmd = {
            "id": 3,
            "method": "Page.startScreencast",
            "params": {
                "format": "jpeg",
                "quality": 80,
                "maxWidth": 1280,
                "maxHeight": 720,
                "everyNthFrame": 1
            }
        }
        await ws.send(json.dumps(screencast_cmd))
        print("[Recorder] Screencast iniciado...")

        try:
            while (time.time() - start_time) < max_seconds:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    data = json.loads(msg)

                    if data.get("method") == "Page.screencastFrame":
                        params = data.get("params", {})
                        session_id = params.get("sessionId")
                        frame_b64 = params.get("data")
                        metadata = params.get("metadata", {})

                        # Acknowledge imediato para receber o próximo frame
                        ack = {
                            "id": 1000 + frame_count,
                            "method": "Page.screencastFrameAck",
                            "params": {"sessionId": session_id}
                        }
                        await ws.send(json.dumps(ack))

                        # Controle de FPS
                        now = time.time()
                        if now - last_frame_time < (1.0 / fps_limit):
                            continue
                        last_frame_time = now

                        frame_count += 1
                        filename = f"frame_{frame_count:05d}.jpg"
                        filepath = os.path.join(frames_dir, filename)

                        with open(filepath, "wb") as f:
                            f.write(base64.b64decode(frame_b64))

                        frame_meta.append({
                            "frame": frame_count,
                            "file": filename,
                            "timestamp": metadata.get("timestamp", now),
                            "elapsed": round(now - start_time, 3)
                        })

                except asyncio.TimeoutError:
                    continue
        finally:
            print(f"[Recorder] Finalizando screencast... Total de frames: {frame_count}")
            await ws.send(json.dumps({"id": 9999, "method": "Page.stopScreencast"}))

    # Salvar metadata
    meta_path = os.path.join(output_dir, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_frames": frame_count,
            "duration": round(time.time() - start_time, 2),
            "frames": frame_meta
        }, f, indent=2)

    # Gerar WebP animado
    if frame_count > 0:
        print("[Recorder] Compilando gravação em WebP animado...")
        try:
            images = []
            for meta in frame_meta:
                p = os.path.join(frames_dir, meta["file"])
                if os.path.exists(p):
                    images.append(Image.open(p))
            if images:
                webp_path = os.path.join(output_dir, "recording.webp")
                duration_per_frame = int((time.time() - start_time) / frame_count * 1000)
                images[0].save(
                    webp_path,
                    format="WEBP",
                    save_all=True,
                    append_images=images[1:],
                    duration=max(duration_per_frame, 50),
                    loop=0
                )
                print(f"[Recorder] Gravacao WebP salva em: {webp_path}")
        except Exception as e:
            print(f"[Recorder] Erro ao compilar WebP: {e}")

    # Gerar HTML Replay Player
    generate_replay_html(output_dir, frame_meta)
    print(f"[Recorder] Player HTML gerado em: {os.path.join(output_dir, 'replay.html')}")
    return frame_count

def generate_replay_html(output_dir, frame_meta):
    files = [m["file"] for m in frame_meta]
    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Screencast Replay - OpenClaw Browser</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; }}
  .container {{ max-width: 1000px; width: 100%; background: #1e293b; border-radius: 12px; padding: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
  h2 {{ margin-top: 0; color: #38bdf8; display: flex; justify-content: space-between; align-items: center; }}
  .screen-box {{ width: 100%; height: 560px; background: #000; border-radius: 8px; overflow: hidden; display: flex; align-items: center; justify-content: center; position: relative; }}
  .screen-box img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}
  .controls {{ margin-top: 15px; display: flex; align-items: center; gap: 12px; }}
  button {{ background: #0284c7; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 14px; }}
  button:hover {{ background: #0369a1; }}
  .timeline {{ flex: 1; }}
  input[type=range] {{ width: 100%; accent-color: #38bdf8; cursor: pointer; }}
  .info {{ font-size: 13px; color: #94a3b8; font-family: monospace; }}
</style>
</head>
<body>
<div class="container">
  <h2>
    <span>📹 Execução de Navegação (Replay)</span>
    <span class="info" id="frame-info">Frame: 0 / {len(files)}</span>
  </h2>
  <div class="screen-box">
    <img id="screen" src="frames/{files[0] if files else ''}" alt="Replay Frame" />
  </div>
  <div class="controls">
    <button id="btn-play">▶ Play</button>
    <button id="btn-prev">⏮</button>
    <button id="btn-next">⏭</button>
    <div class="timeline">
      <input type="range" id="scrubber" min="0" max="{max(len(files)-1, 0)}" value="0">
    </div>
    <select id="speed-sel" style="background:#334155; color:#fff; border:none; padding:8px; border-radius:6px;">
      <option value="0.5">0.5x</option>
      <option value="1" selected>1.0x</option>
      <option value="2">2.0x</option>
      <option value="4">4.0x</option>
    </select>
  </div>
</div>

<script>
  const frames = {json.dumps(files)};
  let currentIndex = 0;
  let isPlaying = false;
  let playInterval = null;
  const imgEl = document.getElementById('screen');
  const scrubber = document.getElementById('scrubber');
  const infoEl = document.getElementById('frame-info');
  const btnPlay = document.getElementById('btn-play');
  const speedSel = document.getElementById('speed-sel');

  function updateFrame(idx) {{
    if (idx < 0 || idx >= frames.length) return;
    currentIndex = idx;
    imgEl.src = 'frames/' + frames[currentIndex];
    scrubber.value = currentIndex;
    infoEl.innerText = `Frame: ${{currentIndex + 1}} / ${{frames.length}}`;
  }}

  function togglePlay() {{
    if (isPlaying) {{
      clearInterval(playInterval);
      isPlaying = false;
      btnPlay.innerText = '▶ Play';
    }} else {{
      isPlaying = true;
      btnPlay.innerText = '⏸ Pausar';
      const speed = parseFloat(speedSel.value);
      const delay = 100 / speed;
      playInterval = setInterval(() => {{
        if (currentIndex < frames.length - 1) {{
          updateFrame(currentIndex + 1);
        }} else {{
          updateFrame(0);
        }}
      }}, delay);
    }}
  }}

  btnPlay.onclick = togglePlay;
  document.getElementById('btn-prev').onclick = () => updateFrame(currentIndex - 1);
  document.getElementById('btn-next').onclick = () => updateFrame(currentIndex + 1);
  scrubber.oninput = (e) => updateFrame(parseInt(e.target.value));
  speedSel.onchange = () => {{
    if (isPlaying) {{
      togglePlay();
      togglePlay();
    }}
  }};
</script>
</body>
</html>"""
    with open(os.path.join(output_dir, "replay.html"), "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    cdp = "127.0.0.1:9223"
    print("[1] Abrindo nova aba limpa para teste de gravacao...")
    tab = open_test_tab(cdp, "https://example.com")
    print(f"Aba criada: {tab.get('id')} - {tab.get('url')}")
    ws_url = tab.get("webSocketDebuggerUrl")
    
    out_dir = os.path.join(r"C:\Users\Olliver_Crypto\.openclaw\workspace\memory\browser_benchmark\test_run_01")
    try:
        frames = asyncio.run(record_screencast(ws_url, out_dir, max_seconds=4, fps_limit=5))
        print(f"Teste concluido com sucesso! Frames: {frames}")
    finally:
        print("[2] Fechando aba de teste...")
        close_tab(cdp, tab.get("id"))
