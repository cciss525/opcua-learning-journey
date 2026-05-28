"""
工厂设备实时监控面板 — Web Dashboard
启动方式: python web_dashboard.py
浏览器打开: http://localhost:8080

前提: 先启动 opcua_server.py (模拟工厂设备)
"""

import asyncio
import json
from asyncua import Client, ua
from aiohttp import web
import pathlib

# ── 全局变量，存最新数据 ──
import time
LATEST_DATA = {}
LAST_UPDATE = 0.0  # 最后一次读到数据的时间戳


async def opcua_poller():
    """每 500ms 从 OPC UA Server 读取所有数据点，更新到 LATEST_DATA"""
    global LATEST_DATA, LAST_UPDATE

    # 定义要读取的所有数据点（NodeId -> 显示元信息）
    NODES = {
        "ns=2;i=3":  ("工位1·气缸",   "位置",      "mm"),
        "ns=2;i=4":  ("工位1·气缸",   "速度",      "mm/s"),
        "ns=2;i=5":  ("工位1·气缸",   "状态",      ""),
        "ns=2;i=7":  ("工位1·伺服电机", "转速",     "RPM"),
        "ns=2;i=8":  ("工位1·伺服电机", "温度",     "°C"),
        "ns=2;i=9":  ("工位1·伺服电机", "负载",     "%"),
        "ns=2;i=10": ("工位1",         "产线状态", ""),
        "ns=2;i=13": ("工位2·传送带",  "速度",     "mm/s"),
        "ns=2;i=14": ("工位2·传送带",  "状态",     ""),
        "ns=2;i=16": ("工位2·机器人",  "X轴",      "mm"),
        "ns=2;i=17": ("工位2·机器人",  "Y轴",      "mm"),
        "ns=2;i=18": ("工位2·机器人",  "Z轴",      "mm"),
        "ns=2;i=19": ("工位2·机器人",  "抓手",     ""),
        "ns=2;i=20": ("工位2",         "产线状态", ""),
    }

    while True:
        try:
            client = Client(url="opc.tcp://localhost:4840")
            async with client:
                print("[OPCUA] 已连接，开始轮询 14 个数据点...")

                while True:
                    success = 0
                    for nid, (group, name, unit) in NODES.items():
                        try:
                            node = client.get_node(nid)
                            val = await asyncio.wait_for(node.read_value(), timeout=0.3)
                            LATEST_DATA[nid] = {
                                "group": group,
                                "name": name,
                                "value": round(val, 1) if isinstance(val, float) else val,
                                "unit": unit,
                            }
                            LAST_UPDATE = time.time()
                            success += 1
                        except (Exception, asyncio.TimeoutError):
                            pass
                    # 所有 14 个节点都读失败 → 连接已断
                    if success == 0:
                        raise ConnectionError("所有节点读取失败")
                    await asyncio.sleep(0.5)

        except Exception as e:
            print(f"[OPCUA] 连接失败({e})，2秒后重试...")
            LATEST_DATA.clear()
            LAST_UPDATE = 0.0
            await asyncio.sleep(2)


# ── 内嵌 HTML 页面 ──
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Factory Monitor — OPC UA 实时监控</title>
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
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, sans-serif;
    min-height: 100vh;
    padding: 20px;
  }
  .header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 24px; padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
  }
  .header h1 { font-size: 22px; font-weight: 600; }
  .status-dot {
    display: inline-block; width: 10px; height: 10px; border-radius: 50%;
    margin-right: 6px;
  }
  .status-dot.online { background: var(--green); box-shadow: 0 0 8px var(--green); }
  .status-dot.offline { background: var(--red); }
  .status-dot.stale { background: var(--yellow); animation: blink 0.8s infinite; }
  @keyframes blink { 50% { opacity: 0.3; } }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
    gap: 20px;
  }
  .station {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
  }
  .station h2 {
    font-size: 15px; font-weight: 600; margin-bottom: 16px;
    padding-bottom: 10px; border-bottom: 1px solid var(--border);
  }
  .device { margin-bottom: 16px; }
  .device-name {
    font-size: 12px; font-weight: 600; color: var(--accent);
    text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;
  }
  .vars {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 8px;
  }
  .var-card {
    background: #0d1117;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px;
    text-align: center;
    transition: border-color 0.3s;
  }
  .var-card.updated { border-color: var(--accent); transition: none; }
  .var-label {
    font-size: 11px; color: var(--muted); margin-bottom: 6px;
  }
  .var-value {
    font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums;
    color: var(--text);
  }
  .var-value.status-1 { color: var(--green); }
  .var-value.status-2 { color: var(--red); }
  .var-value.status-0 { color: var(--yellow); }
  .var-unit { font-size: 11px; color: var(--muted); margin-left: 4px; }
  .footer {
    margin-top: 24px; padding-top: 12px; border-top: 1px solid var(--border);
    font-size: 11px; color: var(--muted); text-align: center;
  }
  .empty-state {
    grid-column: 1 / -1;
    text-align: center; padding: 60px 20px; color: var(--muted);
  }
  .error-banner {
    background: #3d1214; color: var(--red); padding: 10px 16px;
    border-radius: 6px; margin-bottom: 16px; font-size: 13px; display: none;
  }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>Digital Twin — OPC UA 实时监控</h1>
    <span style="font-size:12px;color:var(--muted)">
      模拟工厂设备数据 · opc.tcp://localhost:4840
    </span>
  </div>
  <div style="display:flex;align-items:center;gap:6px;font-size:13px">
    <span class="status-dot" id="status-dot"></span>
    <span id="status-text">连接中...</span>
  </div>
</div>

<div id="error-banner" class="error-banner">OPC UA Server 未运行，请先启动 opcua_server.py</div>

<div class="grid" id="grid">
  <div class="empty-state" id="empty-state">等待数据...</div>
</div>

<div class="footer">
  OPC UA Server: opc.tcp://localhost:4840 | 点击
  <a href="/api/data" target="_blank" style="color:var(--accent)">/api/data</a>
  查看原始 JSON
</div>

<script>
const STATUS_MAP = {0: '停机', 1: '运行中', 2: '故障'};

async function fetchData() {
  try {
    const res = await fetch('/api/data');
    if (!res.ok) throw new Error(res.status);
    const json = await res.json();
    const data = json.data;
    const lastUpdate = json.last_update || 0;
    const age = (Date.now() / 1000) - lastUpdate;  // 数据有多"老"（秒）

    document.getElementById('error-banner').style.display = 'none';

    if (lastUpdate === 0 || age > 5) {
      // 数据太老：离线
      document.getElementById('status-dot').className = 'status-dot offline';
      document.getElementById('status-text').textContent = '离线 · OPC UA Server 无响应';
    } else if (age > 1.5) {
      // 数据稍有延迟：警告
      document.getElementById('status-dot').className = 'status-dot stale';
      document.getElementById('status-text').textContent =
        '延迟 ' + age.toFixed(1) + 's · ' + Object.keys(data).length + ' 个数据点';
    } else {
      document.getElementById('status-dot').className = 'status-dot online';
      document.getElementById('status-text').textContent =
        '在线 · ' + Object.keys(data).length + ' 个数据点';
    }

    render(data);
  } catch (e) {
    document.getElementById('status-dot').className = 'status-dot offline';
    document.getElementById('status-text').textContent = '离线 · Dashboard 未启动';
  }
}

function render(data) {
  if (!data || Object.keys(data).length === 0) {
    document.getElementById('grid').innerHTML =
      '<div class="empty-state">等待 OPC UA Server 连接...</div>';
    return;
  }
  // 按工位和设备分组
  const stations = {};
  for (const [nid, item] of Object.entries(data)) {
    const g = item.group;
    if (!stations[g]) stations[g] = {};
    const devName = g.split('·')[1] || g;
    if (!stations[g][devName]) stations[g][devName] = [];
    stations[g][devName].push(item);
  }

  let html = '';

  for (const [stationName, devices] of Object.entries(stations)) {
    const stationKey = stationName.split('·')[0] || stationName;
    html += `<div class="station">
      <h2>${stationName}</h2>`;

    for (const [devName, vars] of Object.entries(devices)) {
      html += `<div class="device">
        <div class="device-name">${devName}</div>
        <div class="vars">`;

      for (const v of vars) {
        let valCls = '';
        let displayVal = v.value;

        if (v.name === '状态' || v.name === '产线状态' || v.name === '抓手') {
          valCls = ' status-' + v.value;
          displayVal = STATUS_MAP[v.value] ?? v.value;
        }

        const unitSpan = v.unit ? `<span class="var-unit">${v.unit}</span>` : '';

        html += `<div class="var-card" data-nid="${encodeURIComponent(v.name)}">
          <div class="var-label">${v.name}</div>
          <div class="var-value${valCls}">${displayVal}${unitSpan}</div>
        </div>`;
      }

      html += '</div></div>';
    }

    html += '</div>';
  }

  document.getElementById('grid').innerHTML = html;
}

// 每 500ms 拉一次数据
setInterval(fetchData, 500);
fetchData();
</script>
</body>
</html>"""


async def api_data(request):
    """API: 返回当前所有数据和最后更新时间"""
    return web.json_response({
        "last_update": LAST_UPDATE,
        "data": LATEST_DATA,
    })


async def index_page(request):
    """返回主页 HTML"""
    return web.Response(content_type="text/html", text=HTML_PAGE)


async def main():
    print("=" * 55)
    print("  工厂设备实时监控面板")
    print("  前提: 确保 opcua_server.py 已在另一个窗口运行")
    print("=" * 55)

    # 先启动 OPC UA 数据采集
    asyncio.create_task(opcua_poller())

    app = web.Application()
    app.router.add_get("/", index_page)
    app.router.add_get("/api/data", api_data)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8080)
    await site.start()

    print("\n  浏览器打开 →  http://localhost:8080\n")
    print("  按 Ctrl+C 停止\n")

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
