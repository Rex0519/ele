from enum import StrEnum


class AlertType(StrEnum):
    THRESHOLD = "THRESHOLD"
    TREND_SPIKE = "TREND_SPIKE"
    TREND_DROP = "TREND_DROP"
    OFFLINE = "OFFLINE"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


def check_threshold(
    value: float,
    min_val: float | None,
    max_val: float | None,
    severity: str = Severity.WARNING,
) -> dict | None:
    if max_val is not None and value > max_val:
        return {
            "type": AlertType.THRESHOLD,
            "severity": severity,
            "message": f"数值 {value:.2f} 超过上限 {max_val:.2f}",
            "threshold": max_val,
        }
    if min_val is not None and value < min_val:
        return {
            "type": AlertType.THRESHOLD,
            "severity": severity,
            "message": f"数值 {value:.2f} 低于下限 {min_val:.2f}",
            "threshold": min_val,
        }
    return None


def check_trend(
    current: float,
    previous: float,
    spike_ratio: float = 1.5,
    drop_ratio: float = 0.3,
) -> dict | None:
    if previous <= 0:
        return None

    ratio = current / previous
    if ratio > spike_ratio:
        return {
            "type": AlertType.TREND_SPIKE,
            "severity": Severity.WARNING,
            "message": f"同比增长 {(ratio - 1) * 100:.1f}%",
            "threshold": previous * spike_ratio,
        }
    if ratio < drop_ratio:
        return {
            "type": AlertType.TREND_DROP,
            "severity": Severity.WARNING,
            "message": f"同比下降 {(1 - ratio) * 100:.1f}%",
            "threshold": previous * drop_ratio,
        }
    return None
