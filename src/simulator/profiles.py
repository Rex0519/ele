TIME_FACTORS = {
    (0, 6): 0.5,    # 夜间低谷
    (7, 9): 1.3,    # 早高峰
    (10, 17): 1.0,  # 工作时段
    (18, 21): 1.4,  # 晚高峰
    (22, 23): 0.7,  # 夜间过渡
}


def get_time_factor(hour: int) -> float:
    """根据小时返回时段系数"""
    for (start, end), factor in TIME_FACTORS.items():
        if start <= hour <= end:
            return factor
    return 1.0
