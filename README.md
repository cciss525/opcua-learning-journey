# OPC UA 学习之路

> 数字孪生工程师的工业通信协议学习记录
>
> 从 "PLC 信号驱动 3D 模型动一下" 到 "搭建完整数据采集链路"

---

## 项目结构

```
├── src/                          # Python 源码
│   ├── opcua_server.py           # OPC UA 模拟工厂 (两工位, 14个数据点)
│   ├── web_dashboard.py          # 实时监控面板 (OPC UA → HTTP/JSON → 浏览器)
│   ├── opcua_mqtt_bridge.py      # OPC UA → MQTT 桥接
│   └── modbus_gateway.py         # Modbus TCP → OPC UA 协议网关
├── scripts/                      # 脚本工具
│   ├── start.bat                 # 一键启动所有服务
│   ├── stop.bat                  # 一键关闭所有服务
│   └── plc_opcua_list.py         # 生成 PLC OPC UA 支持对照表 Excel
├── docs/                         # 学习笔记
│   ├── OPC_UA_学习笔记_2026-05-26.md
│   └── 数字孪生进阶学习计划_v2.md
├── data/                         # 数据文件
│   └── PLC_OPC_UA_对照表.xlsx     # 12品牌38条目 PLC 支持对照
└── requirements.txt
```

## 已掌握

- **OPC UA Server/Client** — 模拟工厂设备 + 客户端轮询采集
- **Web 实时监控** — aiohttp + 原生 JS，三态显示（在线/延迟/离线）
- **断线重连** — `asyncio.wait_for` 超时 + 全部节点失败检测 + 自动清理
- **协议网关** — Modbus TCP → OPC UA 转换层
- **协议对比** — OPC UA vs HTTP vs MQTT（推模型 vs 拉模型，安全模型对比）
- **PLC 兼容性** — 12 品牌 38 型号 OPC UA 支持情况
- **工厂架构** — IPC/上位机/SCADA/网关 概念辨析

## 学习路线

```
第一阶段 ✅■■■■■■□□□□  OPC UA + MQTT 深化
第二阶段 ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜  USD 资产管线
第三阶段 ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜  物理仿真入门
第四阶段 ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜  合成数据生成
```

---

*2026-05-26 开始 | 机械工程背景 → 数字孪生全栈*
