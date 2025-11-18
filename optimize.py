import numpy as np
from scipy.optimize import differential_evolution
import json
import sys

# 導入我們的模組
from config import (
    CALIBRATION_FILE_PATH, OPTIMIZATION_BOUNDS, 
    get_tou_price, N_VARIABLES
)
from physics_sim import simulate_hour
from forecast_models import get_predicted_static_head, get_target_daily_volume

# --- 全局變數 (儲存校準因子和預測) ---
CALIBRATED_FACTORS = None
HOURLY_STATIC_HEAD = []
TARGET_VOLUME = 0.0

def objective_function(solution_vector):
    """
    DE 演算法的目標函數。
    """
    global CALIBRATED_FACTORS, HOURLY_STATIC_HEAD, TARGET_VOLUME
    
    # 1. 將 96 維向量拆解
    hourly_frequencies = np.reshape(solution_vector, (24, 4))
    
    total_cost = 0.0
    total_volume_m3 = 0.0
    
    # 2. 模擬 24 小時
    for hour in range(24):
        frequencies_this_hour = hourly_frequencies[hour]
        static_head = HOURLY_STATIC_HEAD[hour]
        
        # 執行模擬 (使用已校準的因子)
        power_kw, flow_m3s = simulate_hour(
            frequencies_this_hour,
            static_head,
            CALIBRATED_FACTORS
        )
        
        # 3. 累加成本 (目標)
        price = get_tou_price(hour)
        total_cost += power_kw * price # (kW * 1h * $/kWh)
        
        # 4. 累加流量 (約束)
        total_volume_m3 += flow_m3s * 3600 # (m³/s * 3600 s/h)

    # 5. 計算懲罰
    total_penalty = 0.0
    if total_volume_m3 < TARGET_VOLUME:
        deficit = TARGET_VOLUME - total_volume_m3
        # 懲罰 = (缺少的體積 m³ * 一個大數字)
        total_penalty = deficit * 1000 
        
    # DE 的目標是最小化 (成本 + 懲罰)
    return total_cost + total_penalty

def load_calibration_data():
    """
    載入校準檔案
    """
    try:
        with open(CALIBRATION_FILE_PATH, 'r') as f:
            factors = json.load(f)
        print(f"成功載入校準檔案: {CALIBRATION_FILE_PATH}")
        return factors
    except FileNotFoundError:
        print(f"錯誤: 找不到校準檔案 {CALIBRATION_FILE_PATH}")
        print("請先執行 'python calibrate.py' 產生此檔案。")
        sys.exit(1) # 終止程式

def run_de_optimization():
    """
    執行差分進化演算法
    """
    print("開始執行差分進化 (DE) 最佳化...")
    print(f"求解 {N_VARIABLES} 個變數 (24 小時 * 4 台泵)...")
    
    result = differential_evolution(
        func=objective_function,
        bounds=OPTIMIZATION_BOUNDS,
        strategy='best1bin',
        maxiter=1000,       # (可增加迭代次數以獲得更好結果)
        popsize=20,         # (可增加族群大小)
        tol=0.01,
        recombination=0.7,
        mutation=(0.5, 1),
        workers=-1,         # 使用所有 CPU 核心並行計算
        disp=True           # 顯示進度
    )
    
    return result

if __name__ == "__main__":
    # --- 步驟 1: 載入校準因子 ---
    CALIBRATED_FACTORS = load_calibration_data()
    
    # --- 步驟 2: 取得未來 24 小時的預測 ---
    # (我們在 DE 執行前先算好，避免在目標函數中重複計算)
    print("正在取得未來 24 小時的預測...")
    HOURLY_STATIC_HEAD = [get_predicted_static_head(h) for h in range(24)]
    TARGET_VOLUME = get_target_daily_volume()
    print(f"每日目標抽水量: {TARGET_VOLUME:.2f} m³")

    # --- 步驟 3: 執行 DE 演算法 ---
    de_result = run_de_optimization()
    
    # --- 步驟 4: 顯示結果 ---
    if de_result.success:
        print("\n--- 最佳化成功! ---")
        best_schedule_vector = de_result.x
        best_cost_and_penalty = de_result.fun
        
        # 重新計算一次最佳解的詳細資訊
        best_schedule = np.reshape(best_schedule_vector, (24, 4))
        
        print(f"最低總成本 (含懲罰): {best_cost_and_penalty:.2f}")
        
        print("\n最佳化排程 (小時, 泵1, 泵2, 泵3, 泵4):")
        total_vol = 0
        total_c = 0
        for h in range(24):
            f_h = best_schedule[h]
            h_stat = HOURLY_STATIC_HEAD[h]
            p, q = simulate_hour(f_h, h_stat, CALIBRATED_FACTORS)
            vol = q * 3600
            cost = p * get_tou_price(h)
            
            total_vol += vol
            total_c += cost
            
            freq_str = [f"{f:.1f}" for f in f_h]
            print(f"H{h:02d}: {freq_str} | 靜揚程:{h_stat:.2f}m | 流量:{q*3600:.1f} m³ | 成本:{cost:.2f}")

        print("\n--- 最終模擬結果 ---")
        print(f"總抽水量: {total_vol:.2f} m³ (目標: {TARGET_VOLUME:.2f} m³)")
        print(f"總電費: {total_c:.2f}")

    else:
        print("\n--- 最佳化失敗 ---")
        print(de_result.message)