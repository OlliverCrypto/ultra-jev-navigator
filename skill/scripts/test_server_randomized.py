import http.server
import socketserver
import threading
import random
import time

PORT = 18901

def get_randomized_scenario1_html():
    decoys_before = [
        '<div style="margin-bottom:10px;"><input type="text" placeholder="Filtrar por categoria (Ex: DeFi, Layer1)" style="padding:8px; width:60%;"> <button style="padding:8px;">Filtrar</button></div>',
        '<div style="margin-bottom:10px;"><input type="text" placeholder="Código de indicação / cupom" style="padding:8px; width:60%;"> <button style="padding:8px;">Aplicar</button></div>'
    ]
    decoys_after = [
        '<div style="margin-top:15px;"><button style="padding:8px; background:#64748b; color:white; border:none; border-radius:4px;">Limpar Histórico de Busca</button> <button style="padding:8px; background:#64748b; color:white; border:none; border-radius:4px;">Exportar CSV</button></div>'
    ]

    random.shuffle(decoys_before)
    
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Cenário 1 [Randomizado Anti-Memorização]: Busca de Cotação</title>
<style>
  body {{ font-family: sans-serif; margin: 30px; background: #0f172a; color: #f8fafc; }}
  .box {{ background: #1e293b; padding: 24px; border-radius: 8px; max-width: 650px; border: 1px solid #334155; }}
  input {{ padding: 10px; font-size: 15px; border: 1px solid #475569; border-radius: 4px; background: #0f172a; color: white; }}
  button {{ padding: 10px 18px; font-size: 15px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; }}
  .results {{ margin-top: 20px; display: none; background: #0f172a; padding: 16px; border-radius: 6px; border: 1px solid #22c55e; }}
  .badge {{ background: #166534; color: #4ade80; padding: 3px 8px; border-radius: 4px; font-weight: bold; }}
</style>
</head>
<body>
<div class="box">
  <h2 style="color:#38bdf8;">Terminal de Liquidez On-Chain (Layout Embaralhado)</h2>
  <p style="color:#94a3b8;">Ambiente de teste dinâmico com elementos decoy para prevenção de memorização de índices.</p>

  <!-- Decoys Injetados -->
  {''.join(decoys_before)}

  <div style="margin: 15px 0; padding: 15px; background: #334155; border-radius: 6px;">
    <label style="display:block; margin-bottom:6px; font-weight:bold;">Localizar Cotação de Ativo Cripto:</label>
    <input type="text" id="random_input_{random.randint(100,999)}" name="target_search_ticker" placeholder="Digite o ticker desejado (ex: BTC, ETH)" style="width: 65%;">
    <button id="random_btn_{random.randint(100,999)}" onclick="pesquisarAtivo()">Consultar Ativo</button>
  </div>

  {''.join(decoys_after)}

  <div id="results" class="results">
    <h3>Cotação Oficial: <span id="res-ticker">BTC/USD</span></h3>
    <p>Preço de Execução: <span class="badge" id="res-price">$68,450.00</span></p>
    <p>Sinal Confirmado: <strong>ALTA LIQUIDEZ</strong></p>
  </div>
</div>

<script>
function pesquisarAtivo() {{
  const inp = document.querySelector('input[name="target_search_ticker"]');
  const val = inp.value.trim().toUpperCase();
  if (!val) return;
  document.getElementById('res-ticker').innerText = val + '/USD';
  document.getElementById('results').style.display = 'block';
}}
</script>
</body>
</html>
"""
    return html

def get_randomized_scenario2_html():
    fields = [
        ('pair', '<div style="margin-bottom:12px;"><label style="display:block; font-weight:bold;">Par de Negociação:</label><select name="pair_select" style="width:100%; padding:8px;"><option value="">Selecione...</option><option value="BTC-PERP">BTC-PERP</option><option value="ETH-PERP">ETH-PERP</option></select></div>'),
        ('size', '<div style="margin-bottom:12px;"><label style="display:block; font-weight:bold;">Quantidade de Contratos:</label><input type="text" name="contracts_amount" placeholder="Ex: 2.5" style="width:100%; padding:8px; box-sizing:border-box;"></div>'),
        ('decoy_leverage', '<div style="margin-bottom:12px;"><label style="display:block; font-weight:bold;">Alavancagem Máxima Desejada:</label><select style="width:100%; padding:8px;"><option value="5x">5x Cross</option><option value="10x">10x Isolated</option><option value="20x">20x High Risk</option></select></div>'),
        ('decoy_note', '<div style="margin-bottom:12px;"><label style="display:block; font-weight:bold;">Nota Operacional Interna:</label><input type="text" placeholder="Observações do trader (opcional)" style="width:100%; padding:8px; box-sizing:border-box;"></div>'),
        ('check', '<div style="margin-bottom:12px;"><label><input type="checkbox" name="risk_check"> Confirmo o dimensionamento de risco</label></div>'),
        ('decoy_email', '<div style="margin-bottom:12px;"><label><input type="checkbox"> Receber comprovante por e-mail</label></div>')
    ]
    random.shuffle(fields)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Cenário 2 [Randomizado Anti-Memorização]: Ordem Derivativos</title>
<style>
  body {{ font-family: sans-serif; margin: 30px; background: #0f172a; color: #f8fafc; }}
  .box {{ background: #1e293b; padding: 24px; border-radius: 8px; max-width: 500px; border: 1px solid #334155; }}
  input[type=text], select {{ border: 1px solid #475569; border-radius: 4px; background: #0f172a; color: white; }}
  button {{ width: 100%; padding: 12px; background: #10b981; color: white; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; }}
  #success-box {{ display:none; background:#064e3b; border:1px solid #10b981; color:#a7f3d0; padding:16px; border-radius:6px; margin-top:16px; }}
</style>
</head>
<body>
<div class="box">
  <h2 style="color:#34d399;">Execução de Ordem Futuros (Campos Embaralhados)</h2>
  <form id="trade-form" onsubmit="event.preventDefault(); submeter();">
    {''.join([f[1] for f in fields])}
    <button type="submit" id="submit_order_btn">Enviar Ordem ao Livro</button>
  </form>
  <div id="success-box">
    [ORDEM CONFIRMADA] ID: <strong id="order-id">ORD-94821</strong> | Status: Executada
  </div>
</div>
<script>
function submeter() {{
  const pair = document.querySelector('select[name="pair_select"]')?.value;
  const size = document.querySelector('input[name="contracts_amount"]')?.value;
  const chk = document.querySelector('input[name="risk_check"]')?.checked;
  if (!pair || !size || !chk) {{
    alert('Preencha os campos obrigatórios!');
    return;
  }}
  document.getElementById('trade-form').style.display = 'none';
  document.getElementById('success-box').style.display = 'block';
}}
</script>
</body>
</html>
"""
    return html

class AntiMemoHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/scenario1":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_randomized_scenario1_html().encode("utf-8"))
        elif self.path == "/scenario2":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_randomized_scenario2_html().encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    server = socketserver.TCPServer(("127.0.0.1", PORT), AntiMemoHandler)
    server.serve_forever()

if __name__ == "__main__":
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    print(f"[AntiMemoServer] Servidor randomizado ouvindo em http://127.0.0.1:{PORT}")
    while True:
        time.sleep(1)
