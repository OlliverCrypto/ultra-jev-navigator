import http.server
import socketserver
import threading
import time

PORT = 18900

SCENARIO1_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Cenario 1: Busca e Extracao</title>
<style>
  body { font-family: sans-serif; margin: 40px; background: #f1f5f9; color: #0f172a; }
  .box { background: white; padding: 24px; border-radius: 8px; max-width: 600px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
  input { width: 70%; padding: 10px; font-size: 16px; border: 1px solid #cbd5e1; border-radius: 4px; }
  button { padding: 10px 20px; font-size: 16px; background: #2563eb; color: white; border: none; border-radius: 4px; cursor: pointer; }
  .results { margin-top: 20px; display: none; }
  .item { padding: 12px; border-bottom: 1px solid #e2e8f0; }
  .badge { background: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 9999px; font-weight: bold; }
</style>
</head>
<body>
<div class="box">
  <h1>Portal de Ativos Financeiros</h1>
  <p>Digite o ticker do ativo para consultar a cotacao oficial:</p>
  <div>
    <input type="text" id="search-input" placeholder="Ex: BTC, ETH, SOL, PETR4">
    <button id="search-btn" onclick="buscar()">Pesquisar</button>
  </div>
  <div id="results" class="results">
    <div class="item">
      <h3>Ativo: <span id="res-ticker">BTC/USD</span></h3>
      <p>Preco Atual: <span class="badge" id="res-price">$68,450.00</span></p>
      <p id="res-status">Status de liquidez: <strong>Alta Profundidade</strong></p>
    </div>
  </div>
</div>
<script>
function buscar() {
  const val = document.getElementById('search-input').value.trim().toUpperCase();
  if(!val) return;
  document.getElementById('res-ticker').innerText = val + '/USD';
  if(val === 'BTC') document.getElementById('res-price').innerText = '$68,450.00';
  else if(val === 'ETH') document.getElementById('res-price').innerText = '$2,640.00';
  else document.getElementById('res-price').innerText = '$142.50';
  document.getElementById('results').style.display = 'block';
}
</script>
</body>
</html>
"""

SCENARIO2_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Cenario 2: Formulario Multi-etapas</title>
<style>
  body { font-family: sans-serif; margin: 40px; background: #f8fafc; color: #1e293b; }
  .box { background: white; padding: 24px; border-radius: 8px; max-width: 500px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
  .field { margin-bottom: 16px; }
  label { display: block; font-weight: 600; margin-bottom: 6px; }
  input[type=text], select { width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; box-sizing: border-box; }
  button { width: 100%; padding: 12px; background: #059669; color: white; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; }
  #success-msg { display: none; background: #ecfdf5; border: 1px solid #10b981; color: #065f46; padding: 16px; border-radius: 6px; margin-top: 16px; font-weight: bold; }
</style>
</head>
<body>
<div class="box">
  <h2>Ordem de Execucao Algoritmica</h2>
  <form id="order-form" onsubmit="event.preventDefault(); submeter();">
    <div class="field">
      <label for="pair">Par de Negociacao</label>
      <select id="pair">
        <option value="">Selecione...</option>
        <option value="BTC-PERP">BTC-PERP</option>
        <option value="ETH-PERP">ETH-PERP</option>
        <option value="SOL-PERP">SOL-PERP</option>
      </select>
    </div>
    <div class="field">
      <label for="side">Direcao</label>
      <select id="side">
        <option value="LONG">LONG (Compra)</option>
        <option value="SHORT">SHORT (Venda)</option>
      </select>
    </div>
    <div class="field">
      <label for="size">Quantidade (Contratos)</label>
      <input type="text" id="size" placeholder="Ex: 1.5">
    </div>
    <div class="field">
      <label>
        <input type="checkbox" id="confirm-check"> Confirmo o dimensionamento de risco
      </label>
    </div>
    <button type="submit" id="btn-submit">Executar Ordem</button>
  </form>
  <div id="success-msg">
    [SUCESSO] Ordem executada com ID: <span id="order-id">ORD-94821</span>
  </div>
</div>
<script>
function submeter() {
  const pair = document.getElementById('pair').value;
  const size = document.getElementById('size').value;
  const check = document.getElementById('confirm-check').checked;
  if (!pair || !size || !check) {
    alert('Preencha todos os campos obrigatórios!');
    return;
  }
  document.getElementById('order-form').style.display = 'none';
  document.getElementById('success-msg').style.display = 'block';
}
</script>
</body>
</html>
"""

SCENARIO3_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Cenario 3: Feed SPA com Scroll Infinito</title>
<style>
  body { font-family: sans-serif; margin: 0; background: #0f172a; color: #f8fafc; padding: 20px; }
  .feed { max-width: 600px; margin: 0 auto; }
  .card { background: #1e293b; padding: 16px; border-radius: 8px; margin-bottom: 16px; border: 1px solid #334155; }
  .card h3 { margin-top: 0; color: #38bdf8; }
  #target-card { border: 2px solid #f59e0b; background: #1e293b; }
  .target-badge { background: #f59e0b; color: #000; padding: 2px 6px; border-radius: 4px; font-size: 12px; font-weight: bold; }
</style>
</head>
<body>
<div class="feed" id="feed-container">
  <h1>Feed de Sinais On-Chain</h1>
  <div class="card"><h3>Sinal #1: Accumulation Alert</h3><p>Whale address moved 450 BTC to cold storage.</p></div>
  <div class="card"><h3>Sinal #2: Funding Rate Shift</h3><p>Perpetual swap funding rate turned deeply negative.</p></div>
  <div class="card"><h3>Sinal #3: Liquidity Pool Inflow</h3><p>Uniswap V3 pool received $2.5M in stablecoins.</p></div>
  <div class="card"><h3>Sinal #4: Options Open Interest</h3><p>Gamma spike detected at $70,000 strike.</p></div>
  <div class="card"><h3>Sinal #5: Miner Outflow Low</h3><p>Miner balances steady for 14 consecutive days.</p></div>
  <div class="card" id="target-card">
    <h3><span class="target-badge">ALVO CRITICO</span> Sinal #6: Arbitrage Opportunity</h3>
    <p>Spread between Binance e Hyperliquid atingiu 18 bps. Lucro estimado: $14,200.</p>
    <button id="btn-capture" onclick="capturar()">Capturar Arbitragem</button>
    <span id="capture-status" style="display:none; color:#4ade80; font-weight:bold; margin-left:10px;">CAPTURADO COM SUCESSO!</span>
  </div>
</div>
<script>
function capturar() {
  document.getElementById('btn-capture').style.display = 'none';
  document.getElementById('capture-status').style.display = 'inline';
}
</script>
</body>
</html>
"""

class BenchmarkHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/scenario1":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(SCENARIO1_HTML.encode("utf-8"))
        elif self.path == "/scenario2":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(SCENARIO2_HTML.encode("utf-8"))
        elif self.path == "/scenario3":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(SCENARIO3_HTML.encode("utf-8"))
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    server = socketserver.TCPServer(("127.0.0.1", PORT), BenchmarkHandler)
    server.serve_forever()

if __name__ == "__main__":
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    print(f"[TestServer] Servidor de benchmark ouvindo em http://127.0.0.1:{PORT}")
    while True:
        time.sleep(1)
