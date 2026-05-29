"""
OPC UA 采集配置编辑器
启动方式: python src/config_editor.py
浏览器打开: http://localhost:8081
"""

import yaml
import pathlib
from aiohttp import web

CONFIG_PATH = pathlib.Path(__file__).parent.parent / "config.yaml"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>采集配置 & 实时监控</title>
<style>
  :root {
    --bg: #0d1117;
    --card: #161b22;
    --border: #30363d;
    --text: #c9d1d9;
    --accent: #58a6ff;
    --green: #3fb950;
    --red: #f85149;
    --yellow: #d2991d;
    --muted: #8b949e;
    --input-bg: #0d1117;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, sans-serif;
    height: 100vh;
    display: flex;
    overflow: hidden;
  }

  /* ── 左侧：配置面板 (可滚动) ── */
  #left-panel {
    width: 520px; min-width: 520px;
    padding: 20px;
    overflow-y: auto;
    border-right: 1px solid var(--border);
    height: 100vh;
  }
  #left-panel h1 { font-size: 18px; margin-bottom: 4px; }
  #left-panel .subtitle { font-size: 11px; color: var(--muted); margin-bottom: 16px; }
  .section {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
  }
  .section h2 {
    font-size: 13px; margin-bottom: 10px; padding-bottom: 6px;
    border-bottom: 1px solid var(--border);
  }
  .row { display: flex; gap: 10px; margin-bottom: 8px; align-items: center; }
  .row label { font-size: 11px; color: var(--muted); min-width: 75px; text-align: right; }
  input, select {
    background: var(--input-bg);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 5px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-family: 'Consolas', monospace;
  }
  input:focus { border-color: var(--accent); outline: none; }
  input.wide { flex: 1; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th { text-align: left; font-size: 10px; color: var(--muted); padding: 4px 6px; border-bottom: 1px solid var(--border); }
  td { padding: 3px 6px; }
  td input { width: 100%; }
  button {
    padding: 6px 16px; border: none; border-radius: 5px;
    font-size: 12px; cursor: pointer; font-weight: 600;
  }
  .btn-save { background: var(--green); color: #000; }
  .btn-add { background: var(--accent); color: #000; font-size: 11px; padding: 4px 10px; }
  .btn-del { background: var(--red); color: #fff; padding: 3px 8px; font-size: 10px; border-radius: 3px; }
  .toast {
    position: fixed; top: 16px; left: 50%; transform: translateX(-50%);
    padding: 10px 20px; border-radius: 6px; font-size: 13px;
    display: none; z-index: 999;
  }
  .toast.ok { background: #1a3a1a; border: 1px solid var(--green); color: var(--green); }
  .toast.err { background: #3a1a1a; border: 1px solid var(--red); color: var(--red); }

  /* ── 右侧：实时数据 ── */
  #right-panel {
    flex: 1;
    padding: 20px;
    overflow-y: auto;
    height: 100vh;
  }
  #right-panel h2 { font-size: 16px; margin-bottom: 4px; }
  .live-status {
    font-size: 12px; margin-bottom: 16px; display: flex; align-items: center; gap: 8px;
  }
  .status-dot {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  }
  .status-dot.online { background: var(--green); box-shadow: 0 0 6px var(--green); }
  .status-dot.offline { background: var(--red); }
  .status-dot.stale { background: var(--yellow); animation: blink 0.8s infinite; }
  @keyframes blink { 50% { opacity: 0.3; } }
  .data-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 12px;
  }
  .data-group {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px;
  }
  .data-group h3 { font-size: 12px; color: var(--accent); margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px; }
  .data-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 5px 0; border-bottom: 1px solid rgba(48,54,61,0.5);
    font-size: 13px;
  }
  .data-row:last-child { border-bottom: none; }
  .data-name { color: var(--muted); font-size: 12px; }
  .data-value { font-weight: 700; font-variant-numeric: tabular-nums; }
  .data-value.status-1 { color: var(--green); }
  .data-value.status-2 { color: var(--red); }
  .empty-state {
    display: flex; align-items: center; justify-content: center;
    height: 200px; color: var(--muted); font-size: 14px;
  }
</style>
</head>
<body>

<!-- ═══ 左侧：配置 ═══ -->
<div id="left-panel">
  <h1>采集配置编辑器</h1>
  <div class="subtitle">修改后点「保存配置」，重启采集程序生效</div>

  <div class="section">
    <h2>OPC UA 连接</h2>
    <div class="row">
      <label>端点地址</label>
      <input id="endpoint" class="wide" placeholder="opc.tcp://192.168.1.100:4840">
    </div>
    <div class="row">
      <label>轮询间隔(秒)</label>
      <input id="poll_interval" placeholder="0.5" style="width:100px">
    </div>
  </div>

  <div class="section">
    <h2>数据库连接</h2>
    <div class="row">
      <label>驱动</label>
      <input id="db_driver" style="width:260px">
    </div>
    <div class="row">
      <label>服务器</label>
      <input id="db_server" style="width:260px">
    </div>
    <div class="row">
      <label>数据库名</label>
      <input id="db_database" style="width:180px">
    </div>
  </div>

  <div class="section">
    <h2>采集数据点 <button class="btn-add" onclick="addRow()">+ 添加</button></h2>
    <table>
      <thead>
        <tr><th>NodeId</th><th>分组</th><th>变量名</th><th>单位</th><th></th></tr>
      </thead>
      <tbody id="node-table"></tbody>
    </table>
  </div>

  <div style="display:flex;gap:10px;margin-top:12px">
    <button class="btn-save" onclick="saveConfig()">保存配置</button>
    <span id="save-status" style="font-size:12px;color:var(--muted);line-height:32px"></span>
  </div>
</div>

<!-- ═══ 右侧：实时数据 ═══ -->
<div id="right-panel">
  <h2>实时数据预览</h2>
  <div class="live-status">
    <span class="status-dot offline" id="status-dot"></span>
    <span id="status-text" style="font-size:12px;color:var(--muted)">等待 web_dashboard...</span>
  </div>
  <div class="data-grid" id="data-grid">
    <div class="empty-state">启动 web_dashboard.py 后自动显示</div>
  </div>
</div>

<div id="toast" class="toast"></div>

<script>
const STATUS_MAP = {0: '停机', 1: '运行中', 2: '故障'};

// ═══════ 配置面板逻辑 ═══════

async function loadConfig() {
  const res = await fetch('/api/config');
  const cfg = await res.json();
  document.getElementById('endpoint').value = cfg.opcua.endpoint || '';
  document.getElementById('poll_interval').value = cfg.opcua.poll_interval || 0.5;
  document.getElementById('db_driver').value = cfg.database.driver || '';
  document.getElementById('db_server').value = cfg.database.server || '';
  document.getElementById('db_database').value = cfg.database.database || '';
  renderNodes(cfg.nodes || []);
}

function renderNodes(nodes) {
  const tbody = document.getElementById('node-table');
  tbody.innerHTML = nodes.map((n, i) => `
    <tr>
      <td><input value="${esc(n.id)}" data-field="id"></td>
      <td><input value="${esc(n.group)}" data-field="group"></td>
      <td><input value="${esc(n.name)}" data-field="name"></td>
      <td><input value="${esc(n.unit)}" data-field="unit" style="width:60px"></td>
      <td><button class="btn-del" onclick="this.closest('tr').remove()">X</button></td>
    </tr>
  `).join('');
}

function esc(s) { return (s || '').replace(/"/g, '&quot;'); }

function addRow() {
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><input value="" data-field="id" placeholder="ns=2;i=3"></td>
    <td><input value="" data-field="group" placeholder="工位1·气缸"></td>
    <td><input value="" data-field="name" placeholder="位置"></td>
    <td><input value="" data-field="unit" style="width:60px" placeholder="mm"></td>
    <td><button class="btn-del" onclick="this.closest('tr').remove()">X</button></td>
  `;
  document.getElementById('node-table').appendChild(tr);
}

async function saveConfig() {
  const cfg = {
    opcua: {
      endpoint: document.getElementById('endpoint').value,
      poll_interval: parseFloat(document.getElementById('poll_interval').value) || 0.5,
    },
    database: {
      driver: document.getElementById('db_driver').value,
      server: document.getElementById('db_server').value,
      database: document.getElementById('db_database').value,
      trusted_connection: 'yes',
    },
    nodes: [],
  };

  document.querySelectorAll('#node-table tr').forEach(row => {
    const idEl = row.querySelector('[data-field="id"]');
    if (!idEl || !idEl.value.trim()) return;
    cfg.nodes.push({
      id: idEl.value.trim(),
      group: (row.querySelector('[data-field="group"]')||{}).value || '',
      name: (row.querySelector('[data-field="name"]')||{}).value || '',
      unit: (row.querySelector('[data-field="unit"]')||{}).value || '',
    });
  });

  const res = await fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cfg),
  });

  if (res.ok) {
    showToast('配置已保存', 'ok');
  } else {
    showToast('保存失败: ' + (await res.text()), 'err');
  }
}

function showToast(msg, type) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast ' + type;
  t.style.display = 'block';
  setTimeout(() => { t.style.display = 'none'; }, 2000);
}

// ═══════ 实时数据面板（从 web_dashboard 拉） ═══════

async function fetchLiveData() {
  try {
    const res = await fetch('/api/live-data');
    if (!res.ok) throw new Error('offline');
    const json = await res.json();
    const data = json.data;
    const age = (Date.now() / 1000) - (json.last_update || 0);

    if (json.last_update === 0 || age > 5) {
      document.getElementById('status-dot').className = 'status-dot offline';
      document.getElementById('status-text').textContent = '离线 · OPC UA Server 无响应';
    } else if (age > 1.5) {
      document.getElementById('status-dot').className = 'status-dot stale';
      document.getElementById('status-text').textContent = '延迟 ' + age.toFixed(1) + 's';
    } else {
      document.getElementById('status-dot').className = 'status-dot online';
      document.getElementById('status-text').textContent = '在线 · ' + Object.keys(data).length + ' 个数据点';
    }

    renderLiveData(data);
  } catch (e) {
    document.getElementById('status-dot').className = 'status-dot offline';
    document.getElementById('status-text').textContent = 'web_dashboard 未启动 (端口 8080)';
    document.getElementById('data-grid').innerHTML = '<div class="empty-state">启动 web_dashboard.py 后自动显示实时数据</div>';
  }
}

function renderLiveData(data) {
  if (!data || Object.keys(data).length === 0) {
    document.getElementById('data-grid').innerHTML = '<div class="empty-state">等待数据...</div>';
    return;
  }

  const groups = {};
  for (const [nid, item] of Object.entries(data)) {
    const g = item.group;
    if (!groups[g]) groups[g] = [];
    groups[g].push(item);
  }

  let html = '';
  for (const [groupName, items] of Object.entries(groups)) {
    html += `<div class="data-group"><h3>${groupName}</h3>`;
    for (const v of items) {
      let valCls = '';
      let displayVal = v.value;
      if (['状态','产线状态','抓手'].includes(v.name)) {
        valCls = ' status-' + v.value;
        displayVal = STATUS_MAP[v.value] ?? v.value;
      }
      const unitSpan = v.unit ? `<span style="color:var(--muted);font-size:11px">${v.unit}</span>` : '';
      html += `<div class="data-row">
        <span class="data-name">${v.name}</span>
        <span class="data-value${valCls}">${displayVal} ${unitSpan}</span>
      </div>`;
    }
    html += '</div>';
  }
  document.getElementById('data-grid').innerHTML = html;
}

// ── 启动 ──
loadConfig();
fetchLiveData();
setInterval(fetchLiveData, 500);
</script>
</body>
</html>"""


async def api_get_config(request):
    """返回当前配置 JSON"""
    cfg = load_config()
    return web.json_response(cfg)


async def api_save_config(request):
    """保存配置到 config.yaml"""
    try:
        cfg = await request.json()
        save_config(cfg)
        return web.Response(text="OK")
    except Exception as e:
        return web.Response(text=str(e), status=400)


async def api_live_data(request):
    """代理转发 web_dashboard 的数据，解决跨域"""
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8080/api/data", timeout=2) as resp:
                data = await resp.json()
                return web.json_response(data)
    except Exception:
        return web.json_response({"last_update": 0, "data": {}})


async def index_page(request):
    return web.Response(content_type="text/html", text=HTML_PAGE)


async def main():
    print("=" * 50)
    print("  采集配置编辑器")
    print("  浏览器打开 →  http://localhost:8081")
    print("  需要: opcua_server.py + web_dashboard.py 已在运行")
    print("=" * 50)

    app = web.Application()
    app.router.add_get("/", index_page)
    app.router.add_get("/api/config", api_get_config)
    app.router.add_post("/api/config", api_save_config)
    app.router.add_get("/api/live-data", api_live_data)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8081)
    await site.start()

    print("\n  按 Ctrl+C 停止\n")
    await asyncio.Event().wait()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
