# calibrate.py
import pandas as pd
import numpy as np
from scipy.optimize import minimize
import json
from physics_sim import simulate_hour
from config import PROCESSED_DATA_PATH, CALIBRATION_FILE_PATH

def calibration_loss(x, df):
    """
    誤差函數：計算「模擬結果」與「歷史數據」的差距。
    Minimize 會不斷調整 x 來讓這個回傳值變小。
    """
    # 解析未知數向量 x
    L_out = x[0]      # 未知數 1: 固定的出水口高程
    k = x[1]          # 未知數 2: 系統管損係數
    
    # 封裝衰退因子
    factors = {
        'pump1_dH': x[2], 'pump1_dQ': x[3],
        'pump2_dH': x[4], 'pump2_dQ': x[5],
        'pump3_dH': x[6], 'pump3_dQ': x[7]
    }
    
    total_error = 0.0
    
    # 為了加速校準，我們不跑全部數據，隨機抽樣 100 筆
    sample_df = df.sample(n=min(len(df), 100), random_state=42)
    
    for _, row in sample_df.iterrows():
        freqs = [row['f1'], row['f2'], row['f3']]
        inlet = row['Inlet_Level']
        
        # 1. 計算當下的靜揚程 (未知 L_out - 已知 Inlet)
        H_stat = L_out - inlet
        
        # 2. 跑模擬
        H_sim, Q_sim, _ = simulate_hour(freqs, H_stat, factors, k)
        
        # 3. 計算誤差
        #    這裡我們專注於讓 "模擬總流量" 逼近 "真實總流量 (CMS)"
        Q_real = row['Q_total_m3s']
        
        if Q_real > 0:
            # 使用相對誤差平方 ((Sim - Real) / Real)^2
            err_Q = ((Q_sim - Q_real) / Q_real) ** 2
            total_error += err_Q

    return total_error

if __name__ == "__main__":
    print("開始系統校準...")
    try:
        df = pd.read_csv(PROCESSED_DATA_PATH)
    except FileNotFoundError:
        print("錯誤：找不到資料。請先執行 process_data.py")
        exit()
    
    # --- 設定初始猜測值 (Initial Guess) ---
    # [L_out, k,  p1_dH, p1_dQ, p2_dH, p2_dQ, p3_dH, p3_dQ]
    # 假設出水口海拔約 20m, K值約 50, 衰退因子皆為 1.0
    x0 = [20.0, 50.0,  1.0, 1.0,  1.0, 1.0,  1.0, 1.0]
    
    # --- 設定變數範圍 (Bounds) ---
    bnds = [
        (5.0, 100.0),   # L_out: 5m ~ 100m
        (1.0, 500.0),   # k: 1 ~ 500 (範圍設寬一點)
        (0.7, 1.1), (0.7, 1.1), # Pump 1 衰退因子 (0.7代表衰退30%)
        (0.7, 1.1), (0.7, 1.1), # Pump 2
        (0.7, 1.1), (0.7, 1.1)  # Pump 3
    ]
    
    print("正在最佳化參數 (這可能需要幾分鐘)...")
    # 使用 L-BFGS-B 演算法進行數值最佳化
    res = minimize(calibration_loss, x0, args=(df,), bounds=bnds, method='L-BFGS-B')
    
    print("\n校準完成!")
    print(f"成功狀態: {res.success}")
    print(f"訊息: {res.message}")
    print(f"最佳參數: {res.x}")
    
    # --- 儲存結果 ---
    result_dict = {
        'L_out_const': res.x[0],
        'system_k': res.x[1],
        'pump1_dH': res.x[2], 'pump1_dQ': res.x[3],
        'pump2_dH': res.x[4], 'pump2_dQ': res.x[5],
        'pump3_dH': res.x[6], 'pump3_dQ': res.x[7]
    }
    
    import json
    with open(CALIBRATION_FILE_PATH, 'w') as f:
        json.dump(result_dict, f, indent=4)
    print(f"校準參數已儲存至 {CALIBRATION_FILE_PATH}")