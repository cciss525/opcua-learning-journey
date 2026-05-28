import asyncio
from asyncua import Server, ua
import random

async def main():
    server = Server()
    server.set_endpoint("opc.tcp://0.0.0.0:4840")
    server.set_server_name("Factory Simulator")
    await server.init()

    idx = await server.register_namespace("http://factory.sim")
    objects = server.get_objects_node()

    D = ua.VariantType.Double   # 浮点数类型
    I = ua.VariantType.Int32    # 整数类型

    # ========== Station01 ==========
    station01 = await objects.add_object(idx, "Station01")

    cyl = await station01.add_object(idx, "Cylinder_01")
    cyl_pos = await cyl.add_variable(idx, "Position", 0.0, datatype=D)
    cyl_spd = await cyl.add_variable(idx, "Speed", 0.0, datatype=D)
    cyl_sts = await cyl.add_variable(idx, "Status", 0, datatype=I)

    motor = await station01.add_object(idx, "ServoMotor_01")
    motor_rpm  = await motor.add_variable(idx, "ActualRPM", 0.0, datatype=D)
    motor_temp = await motor.add_variable(idx, "Temperature", 0.0, datatype=D)
    motor_load = await motor.add_variable(idx, "Load", 0.0, datatype=D)

    line_status = await station01.add_variable(idx, "LineStatus", 0, datatype=I)

    for v in [cyl_pos, cyl_spd, cyl_sts, motor_rpm, motor_temp, motor_load, line_status]:
        await v.set_writable()

    # ========== Station02 ==========
    station02 = await objects.add_object(idx, "Station02")

    conveyor = await station02.add_object(idx, "Conveyor_01")
    conv_spd = await conveyor.add_variable(idx, "Speed", 0.0, datatype=D)
    conv_sts = await conveyor.add_variable(idx, "Status", 0, datatype=I)

    robot = await station02.add_object(idx, "Robot_01")
    robot_x = await robot.add_variable(idx, "AxisX", 0.0, datatype=D)
    robot_y = await robot.add_variable(idx, "AxisY", 0.0, datatype=D)
    robot_z = await robot.add_variable(idx, "AxisZ", 0.0, datatype=D)
    robot_grip = await robot.add_variable(idx, "Gripper", 0, datatype=I)

    line2_status = await station02.add_variable(idx, "LineStatus", 0, datatype=I)

    for v in [conv_spd, conv_sts, robot_x, robot_y, robot_z, robot_grip, line2_status]:
        await v.set_writable()

    await server.start()
    print("OPC UA Server started: opc.tcp://0.0.0.0:4840")
    print("Stations: Station01(Cylinder+Motor), Station02(Conveyor+Robot)")
    print("Press Ctrl+C to stop\n")

    t = 0.0
    while True:
        # --- Station01: 气缸往返运动 ---
        pos = await cyl_pos.read_value()
        if pos >= 100.0:
            await cyl_sts.write_value(2)
            await cyl_spd.write_value(-30.0)
        elif pos <= 0.0:
            await cyl_sts.write_value(1)
            await cyl_spd.write_value(30.0)

        new_pos = pos + (await cyl_spd.read_value()) * 0.1
        await cyl_pos.write_value(float(round(max(0.0, min(100.0, new_pos)), 1)))

        # --- Station01: 电机数据 ---
        await motor_rpm.write_value(round(1450.0 + random.uniform(-20, 20), 1))
        await motor_temp.write_value(round(45.0 + random.uniform(-2, 5), 1))
        await motor_load.write_value(round(60.0 + random.uniform(-10, 10), 1))
        await line_status.write_value(1)

        # --- Station02: 传送带 ---
        await conv_spd.write_value(round(500.0 + random.uniform(-10, 10), 1))
        await conv_sts.write_value(1)

        # --- Station02: 机器人 ---
        await robot_x.write_value(round(200.0 + 50.0 * (t % 10) / 10.0, 1))
        await robot_y.write_value(round(100.0 + 30.0 * ((t + 3.0) % 10) / 10.0, 1))
        await robot_z.write_value(round(50.0 + 20.0 * ((t + 6.0) % 10) / 10.0, 1))
        await robot_grip.write_value(1 if t % 2 < 1 else 0)
        await line2_status.write_value(1 if random.random() > 0.05 else 2)

        t += 0.1
        await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(main())
