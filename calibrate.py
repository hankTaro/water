import pandas as pd
import numpy as np
from scipy.optimize import minimize
import json
from physics_sim import simulate_hour # 導入我們的模擬器
from config import HISTORICAL_DATA_PATH, CALIBRATION_FILE_PATH

def load_historical_data():
    """
    載入並清理歷史數據
    """
    try:
        df = pd.read_csv(HISTORICAL_DATA_PATH)
    except FileNotFoundError:
        print(f"錯誤: 找不到歷史數據檔案 {HISTORICAL_DATA_PATH}")
        print("請先建立此檔案。")
        return None
    
    # 【您必須確保】CSV 檔案的欄位名稱正確
    required_cols = ['f1', 'f2', 'f3', 'f4', 'H_static', 'H_total_measured', 'Q_total_measured'] # H_total_measured 如果壓力錶單位是 kg/cm²： H_total_measured (m) = 壓力錶讀數 * 10 (例如：讀數 3.1 kg/cm² 應記錄為 31.0 m)
    if not all(col in df.columns for col in required_cols):
        print(f"錯誤: CSV 檔案缺少必要欄位。需要: {required_cols}")
        return None
        
    return df

def calibration_error_function(factors_array):
    """
    最佳化演算法 (minimize) 會呼叫的誤差函數。
    """
    # 1. 將陣列轉換回易於讀取的字典
    #    (假設 4 台泵，每台 2 個因子 dH, dQ)
    factors_dict = {
        'pump1_dH': factors_array[0], 'pump1_dQ': factors_array[1],
        'pump2_dH': factors_array[2], 'pump2_dQ': factors_array[3],
        'pump3_dH': factors_array[4], 'pump3_dQ': factors_array[5],
        'pump4_dH': factors_array[6], 'pump4_dQ': factors_array[7],
    }
    
    global historical_df # 重複使用已載入的數據
    total_error = 0.0
    
    # 2. 迭代所有歷史數據點
    for _, row in historical_df.iterrows():
        
        frequencies = [row['f1'], row['f2'], row['f3'], row['f4']]
        static_head = row['H_static']
        
        # 3. 使用 "當前猜測的衰退因子" 執行模擬
        sim_power, sim_flow = simulate_hour(frequencies, static_head, factors_dict)
        
        # 4. 根據模擬流量 Q_sim，計算模擬揚程 H_sim
        #    (我們必須同時比較 Q 和 H 的誤差)
        from physics_sim import get_system_head
        sim_head = get_system_head(sim_flow, static_head)
        
        # 5. 取得真實測量值
        real_head = row['H_total_measured']
        real_flow = row['Q_total_measured']
        
        # 6. 計算誤差 (正規化平方和誤差)
        #    (避免 Q 和 H 的單位尺度差異過大)
        if real_head > 1.0: # 避免除以 0
            err_H = ((sim_head - real_head) / real_head) ** 2
        else:
            err_H = (sim_head - real_head) ** 2

        if real_flow > 0.01: # 避免除以 0
            err_Q = ((sim_flow - real_flow) / real_flow) ** 2
        else:
            err_Q = (sim_flow - real_flow) ** 2
            
        total_error += err_H + err_Q # 我們同時關心 H 和 Q 的準確性
        
    print(f"測試中... 誤差: {total_error:.4f}") # 顯示進度
    return total_error

if __name__ == "__main__":
    print("開始校準程序...")
    
    historical_df = load_historical_data()
    
    if historical_df is not None:
        # 初始猜測：8 個變數 (d_H1, d_Q1, d_H2, d_Q2 ...)，全部為 1.0 (無衰退)
        initial_guess = [1.0] * 8
        
        # 邊界：衰退因子應介於 0.8 (衰退20%) 到 1.0 (無衰退) 之間
        bounds = [(0.8, 1.0)] * 8
        
        print("執行最佳化 (minimize) 以尋找衰退因子... 這可能需要幾分鐘...")
        
        result = minimize(
            fun=calibration_error_function,
            x0=initial_guess,
            method='L-BFGS-B', # 適合有邊界的最佳化
            bounds=bounds,
            options={'disp': True, 'ftol': 1e-6}
        )
        
        if result.success:
            print("校準成功！")
            best_factors_array = result.x
            best_factors_dict = {
                'pump1_dH': best_factors_array[0], 'pump1_dQ': best_factors_array[1],
                'pump2_dH': best_factors_array[2], 'pump2_dQ': best_factors_array[3],
                'pump3_dH': best_factors_array[4], 'pump3_dQ': best_factors_array[5],
                'pump4_dH': best_factors_array[6], 'pump4_dQ': best_factors_array[7],
            }
            print(f"找到的最佳衰退因子: {best_factors_dict}")
            
            # 將結果儲存為 JSON
            with open(CALIBRATION_FILE_PATH, 'w') as f:
                json.dump(best_factors_dict, f, indent=4)
            print(f"校準結果已儲存至 {CALIBRATION_FILE_PATH}")
            
        else:
            print("校準失敗。")
            print(result.message)