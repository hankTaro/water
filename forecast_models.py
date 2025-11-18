def get_predicted_static_head(hour):
    """
    【您必須提供】預測第 h 小時的靜揚程 (H_static)。
    也就是入水與出水水位差 (m)。
    """
    # 範例：假設靜揚程在 24.5m 和 25.5m 之間變動
    import numpy as np
    return 25.0 + np.sin(hour * 2 * np.pi / 24) * 0.5

def get_target_daily_volume():
    """
    【您必須提供】預測今天的總抽水需求量 (m³)。
    """
    return 50000.0 # 假設固定目標 50,000 m³