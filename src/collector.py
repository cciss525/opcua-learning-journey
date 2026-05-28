"""
OPC UA 数据采集引擎
启动方式: python src/collector.py          # 开始采集
         python src/collector.py --browse # 浏览 PLC 所有节点
配置文件: config.yaml
"""

import asyncio
import json
import time
import sys
import yaml
import pathlib
from asyncua import Client, ua
import pyodbc


def load_config():
    """读取 config.yaml"""
    config_path = pathlib.Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_db_connection(cfg):
    """根据配置建立 SQL Server 连接"""
    db = cfg["database"]
    conn_str = (
        f"DRIVER={{{db['driver']}}};"
        f"SERVER={db['server']};"
        f"DATABASE={db['database']};"
        f"Trusted_Connection={db.get('trusted_connection', 'yes')};"
    )
    return pyodbc.connect(conn_str)


def init_database(conn):
    """创建采集表（不存在则新建）"""
    cursor = conn.cursor()

    # 创建采集数据表
    cursor.execute("""
        IF NOT EXISTS (
            SELECT * FROM sysobjects WHERE name='opcua_data' AND xtype='U'
        )
        CREATE TABLE opcua_data (
            id BIGINT IDENTITY(1,1) PRIMARY KEY,
            server_name NVARCHAR(100),
            node_id NVARCHAR(50),
            group_name NVARCHAR(100),
            var_name NVARCHAR(100),
            value FLOAT,
            unit NVARCHAR(20),
            quality INT DEFAULT 0,
            collected_at DATETIME2 DEFAULT GETDATE()
        )
    """)

    # 加速查询
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='IX_collected_at')
        CREATE INDEX IX_collected_at ON opcua_data(collected_at)
    """)

    conn.commit()
    print("[DB] 数据库初始化完成")


async def browse_nodes(endpoint):
    """浏览 OPC UA Server 的用户变量节点（跳过系统内部节点）"""
    print(f"\n正在浏览: {endpoint}")
    client = Client(url=endpoint)
    async with client:
        root = client.nodes.objects
        children = await root.get_children()
        for child in children:
            name = (await child.read_browse_name()).Name
            if name in ("Server", "Aliases"):
                continue  # 跳过 OPC UA 内部节点
            nid = child.nodeid.to_string()
            print(f"\n[对象] {name}  ({nid})")
            await _browse_folder(client, child, depth=1)


async def _browse_folder(client, folder, depth):
    """递归遍历文件夹，打印所有变量节点"""
    prefix = "  " * depth
    try:
        children = await folder.get_children()
        for child in children:
            node_class = await child.read_node_class()
            name = (await child.read_browse_name()).Name
            nid = child.nodeid.to_string()

            if node_class == ua.NodeClass.Variable:
                try:
                    val = await child.read_value()
                    dtype = (await child.read_data_type_as_varianttype()).name
                    print(f"{prefix}[变量] {name}  NodeId={nid}  类型={dtype}  当前值={val}")
                except Exception:
                    print(f"{prefix}[变量] {name}  NodeId={nid}")
            elif node_class == ua.NodeClass.Object:
                print(f"{prefix}[对象] {name}")
                await _browse_folder(client, child, depth + 1)
    except Exception:
        pass  # 跳过无权限的节点


async def collect(endpoint, nodes, poll_interval, db_conn):
    """主采集循环：轮询 OPC UA 节点并写入数据库"""
    server_name = endpoint.replace("opc.tcp://", "")

    while True:
        try:
            client = Client(url=endpoint)
            async with client:
                print(f"[OPCUA] 已连接: {endpoint}")

                while True:
                    success = 0
                    cursor = db_conn.cursor()

                    for nid, (group, name, unit) in nodes.items():
                        try:
                            node = client.get_node(nid)
                            val = await asyncio.wait_for(node.read_value(), timeout=0.3)

                            display_val = round(val, 1) if isinstance(val, float) else float(val)

                            cursor.execute(
                                "INSERT INTO opcua_data (server_name, node_id, group_name, var_name, value, unit) "
                                "VALUES (?, ?, ?, ?, ?, ?)",
                                (server_name, nid, group, name, display_val, unit),
                            )
                            success += 1

                        except (Exception, asyncio.TimeoutError):
                            pass

                    if success == 0:
                        raise ConnectionError("所有节点读取失败")

                    cursor.commit()
                    if success > 0:
                        print(f"[DB] 写入 {success} 条 | {name}={display_val}", end="\r")
                    await asyncio.sleep(poll_interval)

        except Exception as e:
            print(f"\n[OPCUA] 连接失败({e})，2秒后重试...")
            await asyncio.sleep(2)


async def main():
    cfg = load_config()

    if "--browse" in sys.argv:
        await browse_nodes(cfg["opcua"]["endpoint"])
        return

    endpoint = cfg["opcua"]["endpoint"]
    poll_interval = cfg["opcua"].get("poll_interval", 0.5)

    # 构建 NodeId → (group, name, unit) 映射
    nodes = {}
    for node in cfg["nodes"]:
        nodes[node["id"]] = (node["group"], node["name"], node["unit"])

    print("=" * 55)
    print("  OPC UA 数据采集引擎")
    print(f"  目标: {endpoint}")
    print(f"  数据点: {len(nodes)} 个")
    print(f"  数据库: {cfg['database']['server']}/{cfg['database']['database']}")
    print("=" * 55)

    print("[DB] 连接数据库...")
    db_conn = get_db_connection(cfg)
    init_database(db_conn)
    print("[DB] 连接成功\n")

    await collect(endpoint, nodes, poll_interval, db_conn)


if __name__ == "__main__":
    asyncio.run(main())
