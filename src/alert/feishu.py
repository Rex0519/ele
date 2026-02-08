import httpx


class FeishuSender:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, alerts) -> bool:
        lines = []
        for a in alerts:
            lines.append([{"tag": "text", "text": f"[{a.severity}] {a.message}"}])
            if a.point_id:
                lines.append([{"tag": "text", "text": f"  测点: {a.point_id}"}])

        payload = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": f"电力告警通知 ({len(alerts)}条)",
                        "content": lines,
                    }
                }
            },
        }

        resp = httpx.post(self.webhook_url, json=payload, timeout=10)
        data = resp.json()
        if data.get("code") != 0:
            print(f"[Feishu] send failed: {data}")
            return False
        return True
