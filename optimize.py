# optimize.py
import numpy as np
from scipy.optimize import differential_evolution
import json
from config import MIN_ON_FREQUENCY, PUMP_BOUNDS, get_tou_price
from physics_sim import simulate_hour

# --- 1. 載入校準參數 ---
try:
    with open('data/calibration_results.json') as f:
        CALIB = json.load(f)
    print("成功載入校準參數。")
except FileNotFoundError:
    print("錯誤：找不到校準參數。請先執行 calibrate.py")
    exit()

L_OUT = CALIB['L_out_const']
K_VAL = CALIB['system_k']

# --- 2. 設定目標與預測 ---
# 假設：明日需求量 130,000 CMD
# TODO: 這裡填入當月每日抽水需求量
TARGET_CMD = 130000.0 
TARGET_CMS_TOTAL = TARGET_CMD # 累積量比較時再轉秒或直接比對體積

# 假設：明日入水口水位預測 (簡化為固定 6.0m，實際應為 24 小時陣列)
# TODO: 製作不同月份水圳的高低預設值
def get_predicted_inlet(h):
    return 6.0 

# --- 3. 定義 DE 的目標函數 ---
def objective_function(solution_vector):
    """
    DE 演算法會不斷呼叫此函數，傳入一組 72 維的向量 (24小時*3泵)。
    我們需回傳這組解的 "總成本" (越低越好)。
    """
    # 將一維向量 (72,) 重塑為 (24, 3)
    freq_matrix = solution_vector.reshape((24, 3))
    
    total_cost = 0.0
    total_flow_accumulated = 0.0 # 累積總抽水量 (m3)
    
    for h in range(24):
        raw_freqs = freq_matrix[h]
        
        # --- 關鍵邏輯：起停限制 (30-60Hz) ---
        real_freqs = []
        for f in raw_freqs:
            if f < MIN_ON_FREQUENCY:
                real_freqs.append(0.0) # 強制關機
            else:
                real_freqs.append(f)   # 保持原設定
        
        # 取得該小時預測水位
        inlet = get_predicted_inlet(h)
        # 計算靜揚程
        H_stat = L_OUT - inlet
        
        # 執行物理模擬
        _, q_cms, p_kw = simulate_hour(real_freqs, H_stat, CALIB, K_VAL)
        
        # 累加成本 (kW * 1hr * 電價)
        total_cost += p_kw * get_tou_price(h)
        
        # 累加流量 (m3/s * 3600s = m3)
        total_flow_accumulated += q_cms * 3600
        
    # --- 懲罰函數 (Penalty) ---
    # 如果總抽水量未達標，給予巨額罰款
    penalty = 0.0
    if total_flow_accumulated < TARGET_CMD:
        diff = TARGET_CMD - total_flow_accumulated
        penalty = diff * 1000 # 罰款係數 (可調整)
        
    return total_cost + penalty

if __name__ == "__main__":
    print(f"開始最佳化... 目標流量: {TARGET_CMD} CMD")
    print("正在執行差分進化演算法 (DE)...")
    
    # 設定變數範圍 (24小時 * 3泵)
    bounds = PUMP_BOUNDS * 24
    
    # 執行 DE
    # popsize: 族群大小 (越大越準但越慢)
    # maxiter: 迭代次數
    # workers: -1 代表用盡所有 CPU 核心加速
    res = differential_evolution(
        objective_function, 
        bounds, 
        strategy='best1bin', 
        maxiter=100, 
        popsize=15, 
        workers=-1,
        disp=True
    )
    
    print("\n--- 最佳化結果 ---")
    print(f"最低成本 (含懲罰): {res.fun:.2f}")
    
    # 解析最佳解
    best_schedule = res.x.reshape((24, 3))
    
    # 重新跑一次模擬以顯示詳細數據
    print("\n時段 | 泵1(Hz) | 泵2(Hz) | 泵3(Hz) | 流量(CMD) | 功耗(kW) | 電價")
    total_vol = 0
    total_bill = 0
    
    for h in range(24):
        raw_f = best_schedule[h]
        real_f = [f if f >= MIN_ON_FREQUENCY else 0.0 for f in raw_f]
        
        inlet = get_predicted_inlet(h)
        H_stat = L_OUT - inlet
        _, q_cms, p_kw = simulate_hour(real_f, H_stat, CALIB, K_VAL)
        
        vol_cmd = q_cms * 3600
        cost = p_kw * get_tou_price(h)
        
        total_vol += vol_cmd
        total_bill += cost
        
        print(f"{h:02d}   | {real_f[0]:5.1f} | {real_f[1]:5.1f} | {real_f[2]:5.1f} | {vol_cmd:8.1f} | {p_kw:6.1f} | {cost:5.1f}")
        
    print(f"\n全日總抽水量: {total_vol:.1f} CMD (目標: {TARGET_CMD})")
    print(f"預估總電費: {total_bill:.1f} 元")