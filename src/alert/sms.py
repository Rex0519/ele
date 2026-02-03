from abc import ABC, abstractmethod


class SmsSender(ABC):
    """短信发送抽象基类，具体平台实现后继承此类"""

    @abstractmethod
    async def send(self, phones: list[str], message: str) -> bool:
        """发送短信

        Args:
            phones: 接收手机号列表
            message: 短信内容

        Returns:
            是否发送成功
        """
        pass


class DummySmsSender(SmsSender):
    """占位实现，仅打印日志不实际发送"""

    async def send(self, phones: list[str], message: str) -> bool:
        print(f"[SMS] Would send to {phones}: {message}")
        return True
