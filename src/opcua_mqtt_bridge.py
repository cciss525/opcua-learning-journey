import asyncio
import json
from asyncua import Client, ua
import paho.mqtt.client as mqtt

# OPC UA NodeId (string) -> MQTT Topic 映射
NODE_MAP = {
    # Station01
    "ns=2;i=3":  "factory/lineA/station01/cylinder/position",
    "ns=2;i=4":  "factory/lineA/station01/cylinder/speed",
    "ns=2;i=5":  "factory/lineA/station01/cylinder/status",
    "ns=2;i=7":  "factory/lineA/station01/motor/rpm",
    "ns=2;i=8":  "factory/lineA/station01/motor/temperature",
    "ns=2;i=9":  "factory/lineA/station01/motor/load",
    "ns=2;i=10": "factory/lineA/station01/line_status",
    # Station02
    "ns=2;i=13": "factory/lineA/station02/conveyor/speed",
    "ns=2;i=14": "factory/lineA/station02/conveyor/status",
    "ns=2;i=16": "factory/lineA/station02/robot/axis_x",
    "ns=2;i=17": "factory/lineA/station02/robot/axis_y",
    "ns=2;i=18": "factory/lineA/station02/robot/axis_z",
    "ns=2;i=19": "factory/lineA/station02/robot/gripper",
    "ns=2;i=20": "factory/lineA/station02/line_status",
}

mqtt_client = mqtt.Client()


class SubscriptionHandler:
    def datachange_notification(self, node, val, data):
        node_id = node.nodeid.to_string()
        topic = NODE_MAP.get(node_id)
        if topic is None:
            return

        ts = data.monitored_item.Value.SourceTimestamp
        payload = json.dumps({
            "ts": ts.isoformat() if ts else None,
            "value": val,
            "quality": data.monitored_item.Value.StatusCode.value,
        })
        mqtt_client.publish(topic, payload, qos=1)
        print(f"[MQTT] {topic} = {val}")


async def main():
    mqtt_client.connect("localhost", 1883)
    mqtt_client.loop_start()
    print("MQTT connected: localhost:1883")

    client = Client(url="opc.tcp://localhost:4840")

    async with client:
        print("OPC UA connected: opc.tcp://localhost:4840\n")

        handler = SubscriptionHandler()
        sub = await client.create_subscription(period=200, handler=handler)

        for node_id_str in NODE_MAP:
            try:
                node = client.get_node(node_id_str)
                await sub.subscribe_data_change(
                    node,
                    ua.AttributeIds.Value,
                    queue_size=10,
                    monitoring=ua.MonitoringParameters(
                        sampling_interval=100,
                        queue_size=10,
                    ),
                )
                print(f"Subscribed: {node_id_str}")
            except Exception as e:
                print(f"Failed to subscribe {node_id_str}: {e}")

        print("\nBridge running. Press Ctrl+C to stop.\n")
        while True:
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
