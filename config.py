import numpy as np

# --- 1. 檔案路徑 ---
CALIBRATION_FILE_PATH = 'data/calibration_results.json'
HISTORICAL_DATA_PATH = 'data/historical_data.csv'


# --- 2. 系統物理參數 ---
# 【您必須提供】系統管損係數 k (H = H_static + k * Q^2)
# (注意 Q 的單位！假設 k 是基於 Q (m³/s) 計算的)
SYSTEM_K_VALUE = 28.7 # (請替換成您計算出的 k 值)


# --- 3. 抽水機原廠數據 (Pump Base Curves) ---
# 【您必須提供】您那 8 個 H-Q 點 (或更多)
# 這是 60Hz 基準
PUMP_BASE_CURVES = {
    'pump1': {
        'freq': 60.0,
        'flow': np.array([0, 35775/24, 70590/24, 84360/24, 100433/24, 114599/24, 125432/24, 126821/24]), # m³/hr
        'head': np.array([19.96, 17.27, 15.06, 13.09, 11.06, 9.17, 7.2, 4.82])    # m
    },
    'pump2': {
        'freq': 60.0,
        'flow': np.array([0, 50, 100, 150, 200, 250, 300, 350]), # m³/hr
        'head': np.array([71, 69, 66, 61, 53, 41, 26, 11])    # m (假設 2 號泵稍強)
    },
    'pump3': {
        'freq': 60.0,
        'flow': np.array([0, 25, 50, 75, 100, 125]),           # m³/hr (假設 3 號是小泵)
        'head': np.array([50, 48, 42, 35, 25, 15])            # m
    },
    'pump4': {
        'freq': 60.0,
        'flow': np.array([0, 25, 50, 75, 100, 125]),           # m³/hr (假設 4 號是小泵)
        'head': np.array([50, 48, 42, 35, 25, 15])            # m
    }
}

# 將 m³/hr 轉換為 m³/s
for p_id in PUMP_BASE_CURVES:
    PUMP_BASE_CURVES[p_id]['flow'] /= 3600.0 # 轉換為 m³/s


# --- 4. 電價與最佳化設定 ---
def get_tou_price(hour):
    """
    【您必須提供】根據小時 (0-23) 回傳電價
    """
    if 7 <= hour < 22:
        return 5.0  # 尖峰電價
    else:
        return 2.0  # 離峰電價

# 最佳化邊界 (4 台泵，每台的最小/最大頻率)
PUMP_BOUNDS = [
    (30, 60), # 泵 1
    (30, 60), # 泵 2
    (0, 60),  # 泵 3 (0=可關閉)
    (0, 60)   # 泵 4 (0=可關閉)
]

# 總變數數量 (24 小時 * 4 台泵)
N_VARIABLES = 24 * len(PUMP_BOUNDS)

# 建立 96 維的 DE 邊界
OPTIMIZATION_BOUNDS = []
for _ in range(24):
    OPTIMIZATION_BOUNDS.extend(PUMP_BOUNDS)