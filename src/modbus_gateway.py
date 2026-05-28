"""
Modbus TCP → OPC UA 协议网关
模拟场景: 汇川 H3U/H5U PLC 只支持 Modbus TCP，通过这个网关把 Modbus 数据暴露为 OPC UA 格式

你的数字孪生前端只管用 OPC UA 读数据，不用管底层是 Modbus
"""
import asyncio
import random
from asyncua import Server, ua

# ── 模拟 Modbus 设备的数据字典 ──
# 真实场景这里是通过 pymodbus 模块去读真实 PLC
# 这里用随机数据模拟一个正在运行的设备
MODBUS_MAP = {
    "线圈": {
        "desc": "离散输出 (DO)",
        "address": 0,
        "signals": {
            "Q0.0_急停":           False,   # 00001
            "Q0.1_气缸伸出阀":     True,    # 00002
            "Q0.2_气缸缩回阀":     False,   # 00003
            "Q0.3_传送带启动":     True,    # 00004
            "Q0.4_报警灯":         False,   # 00005
            "Q0.5_蜂鸣器":         False,   # 00006
        }
    },
    "离散输入": {
        "desc": "离散输入 (DI)",
        "address": 1000,
        "signals": {
            "I0.0_原点传感器":     True,    # 10001
            "I0.1_前端传感器":     False,   # 10002
            "I0.2_后端传感器":     True,    # 10003
            "I0.3_安全门":         True,    # 10004
            "I0.4_急停按钮":        False,   # 10005
        }
    },
    "保持寄存器": {
        "desc": "模拟量 (AI/当前值)",
        "address": 40001,
        "signals": {
            "气缸当前位置":         78.5,    # 40001  Float, mm
            "伺服电机当前转速":      1450.0,  # 40003  Float, RPM
            "伺服电机温度":          42.3,    # 40005  Float, °C
            "伺服电机负载率":        65.0,    # 40007  Float, %
            "传送带当前速度":        498.2,   # 40009  Float, mm/s
            "当日产量计数":          1047,    # 40011  Int
            "当日不良计数":          23,      # 40013  Int
            "累计运行时间":          8760,    # 40015  Int, 小时
        }
    },
    "输入寄存器": {
        "desc": "AI 只读",
        "address": 30001,
        "signals": {
            "环境温度":              28.5,    # 30001  Float, °C
            "环境湿度":              65.2,    # 30003  Float, %
        }
    },
}


async def main():
    server = Server()
    server.set_endpoint("opc.tcp://0.0.0.0:4841")
    server.set_server_name("Modbus-to-OPCUA Gateway (Huichuan H3U Sim)")
    await server.init()

    idx = await server.register_namespace("http://modbus.gateway")
    objects = server.get_objects_node()

    D = ua.VariantType.Double
    B = ua.VariantType.Boolean
    I = ua.VariantType.Int32

    # ── 按照 Modbus 数据结构创建 OPC UA 地址空间 ──
    opc_nodes = {}

    for zone_name, zone_info in MODBUS_MAP.items():
        # 创建功能区节点 (如 "线圈", "保持寄存器")
        zone_node = await objects.add_object(idx, zone_name)
        # 添加 Modbus 地址范围和说明
        await zone_node.add_variable(idx, "Modbus地址起始",
                                     float(zone_info["address"]), datatype=D)

        for sig_name, sig_value in zone_info["signals"].items():
            var_node = await zone_node.add_variable(
                idx, sig_name, sig_value,
                datatype=B if isinstance(sig_value, bool) else D
            )
            await var_node.set_writable()
            opc_nodes[sig_name] = var_node

    await server.start()
    print("Modbus → OPC UA Gateway: opc.tcp://0.0.0.0:4841")
    print()
    print("  Address space:")
    for zone_name, zone_info in MODBUS_MAP.items():
        n = len(zone_info["signals"])
        print(f"    {zone_name} (Modbus {zone_info['address']}+) — {n} signals")
    print()
    print("  Press Ctrl+C to stop")

    # ── 模拟 Modbus 数据变化 ──
    t = 0.0
    while True:
        # 模拟气缸伸出→缩回
        cyl_ext = opc_nodes["Q0.1_气缸伸出阀"]
        cyl_ret = opc_nodes["Q0.2_气缸缩回阀"]
        cyl_pos = opc_nodes["气缸当前位置"]

        pos = await cyl_pos.read_value()
        if pos >= 100.0:
            await cyl_ext.write_value(False)
            await cyl_ret.write_value(True)
        elif pos <= 0.0:
            await cyl_ext.write_value(True)
            await cyl_ret.write_value(False)

        speed = 30.0 if await cyl_ext.read_value() else -30.0
        new_pos = max(0.0, min(100.0, pos + speed * 0.1))
        await cyl_pos.write_value(round(new_pos, 1))

        # 模拟传感器感应到工件
        await opc_nodes["I0.0_原点传感器"].write_value(True)
        await opc_nodes["I0.1_前端传感器"].write_value(new_pos > 90)

        # 模拟伺服电机数据
        await opc_nodes["伺服电机当前转速"].write_value(
            round(1450.0 + random.uniform(-20, 20), 1))
        await opc_nodes["伺服电机温度"].write_value(
            round(42.0 + random.uniform(-1, 5), 1))
        await opc_nodes["伺服电机负载率"].write_value(
            round(65.0 + random.uniform(-10, 10), 1))

        # 模拟产量递增
        count = await opc_nodes["当日产量计数"].read_value()
        if random.random() < 0.05:
            await opc_nodes["当日产量计数"].write_value(count + 1)
        if random.random() < 0.01:
            bad = await opc_nodes["当日不良计数"].read_value()
            await opc_nodes["当日不良计数"].write_value(bad + 1)

        # 传感器信号模拟变化
        await opc_nodes["I0.2_后端传感器"].write_value(new_pos < 10)

        t += 0.1
        await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(main())
