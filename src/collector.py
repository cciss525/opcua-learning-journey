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
import logging
from datetime import datetime
import yaml
import pathlib
from asyncua import Client, ua
import pyodbc


def setup_logging():
    """日志同时输出到文件和控制台"""
    log_dir = pathlib.Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"collector_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("collector")


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
    logger.info("数据库初始化完成")


async def browse_nodes(endpoint):
    """浏览 OPC UA Server 的用户变量节点（跳过系统内部节点）"""
    logger.info(f"正在浏览: {endpoint}")
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


class DataChangeHandler:
    """OPC UA 订阅回调：数据有变化才触发，不轮询"""

    def __init__(self, db_conn, server_name, node_info):
        self.db_conn = db_conn
        self.server_name = server_name
        self.node_info = node_info  # {NodeId: (group, name, unit)}
        self.count = 0
        self.bad_count = 0

    def datachange_notification(self, node, val, data):
        """OPC UA 有变化时自动调用此方法"""
        node_id = node.nodeid.to_string()
        info = self.node_info.get(node_id)
        if info is None:
            return

        group, name, unit = info
        dv = data.monitored_item.Value

        try:
            cursor = self.db_conn.cursor()

            if dv.StatusCode.is_good():
                display_val = round(val, 1) if isinstance(val, float) else float(val)
                cursor.execute(
                    "INSERT INTO opcua_data (server_name, node_id, group_name, var_name, value, unit, quality) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (self.server_name, node_id, group, name, display_val, unit, dv.StatusCode.value),
                )

            elif dv.StatusCode.name.startswith("Uncertain"):
                display_val = round(val, 1) if isinstance(val, float) else float(val)
                cursor.execute(
                    "INSERT INTO opcua_data (server_name, node_id, group_name, var_name, value, unit, quality) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (self.server_name, node_id, group, name, display_val, unit, dv.StatusCode.value),
                )
                logger.warning(f"{name} 数据质量不确定: {dv.StatusCode.name}")

            else:
                self.bad_count += 1
                logger.warning(f"{name} 数据质量差: {dv.StatusCode.name}，不入库")
                return

            cursor.commit()
            self.count += 1

        except Exception:
            pass


async def collect(endpoint, nodes, db_conn):
    """主采集循环：订阅 OPC UA 数据变化，有变化才入库"""
    server_name = endpoint.replace("opc.tcp://", "")

    while True:
        try:
            client = Client(url=endpoint)
            async with client:
                logger.info(f"OPC UA 已连接: {endpoint}")

                # 创建订阅处理器
                handler = DataChangeHandler(db_conn, server_name, nodes)
                sub = await client.create_subscription(period=200, handler=handler)

                # 订阅所有配置的数据点
                for nid in nodes:
                    try:
                        node = client.get_node(nid)
                        await sub.subscribe_data_change(
                            node, ua.AttributeIds.Value, queuesize=10, sampling_interval=100
                        )
                    except Exception as e:
                        logger.warning(f"订阅失败 {nid}: {e}")

                logger.info(f"订阅完成: {len(nodes)} 个节点，有变化自动入库")
                logger.info("等待数据变化...")

                # 保持连接，等数据自己来
                while True:
                    await asyncio.sleep(10)

        except Exception as e:
            logger.error(f"连接失败({e})，2秒后重试...")
            await asyncio.sleep(2)


async def main():
    global logger
    logger = setup_logging()

    cfg = load_config()

    if "--browse" in sys.argv:
        await browse_nodes(cfg["opcua"]["endpoint"])
        return

    endpoint = cfg["opcua"]["endpoint"]

    # 构建 NodeId → (group, name, unit) 映射
    nodes = {}
    for node in cfg["nodes"]:
        nodes[node["id"]] = (node["group"], node["name"], node["unit"])

    logger.info("=" * 40)
    logger.info(f"OPC UA 数据采集引擎启动")
    logger.info(f"  目标: {endpoint}")
    logger.info(f"  数据点: {len(nodes)} 个")
    logger.info(f"  数据库: {cfg['database']['server']}/{cfg['database']['database']}")
    logger.info("=" * 40)

    logger.info("连接数据库...")
    db_conn = get_db_connection(cfg)
    init_database(db_conn)
    logger.info("数据库连接成功")

    await collect(endpoint, nodes, db_conn)


if __name__ == "__main__":
    asyncio.run(main())
