import numpy as np
from scipy.optimize import fsolve
from config import PUMP_BASE_CURVES, SYSTEM_K_VALUE

# --- 1. 抽水機物理模型 (相似定律) ---

def get_pump_flow(pump_id, frequency, head, degradation_factors):
    """
    使用相似定律和衰退因子，計算(f, H)下的流量Q。
    """
    if frequency <= 0:
        return 0.0

    # 取得衰退因子
    d_H = degradation_factors[f'pump{pump_id}_dH']
    d_Q = degradation_factors[f'pump{pump_id}_dQ']
    
    # 1. 讀取原廠 60Hz 數據
    curve = PUMP_BASE_CURVES[f'pump{pump_id}']
    base_f = curve['freq']
    
    # 2. 【校準】將原廠數據 "縮水" 到反映老化的狀態
    #    (注意：我們假設 d_H 和 d_Q 是基於 60Hz 的衰退)
    base_H_calibrated = curve['head'] * d_H
    base_Q_calibrated = curve['flow'] * d_Q
    
    # 3. 【相似定律】將 "校準後" 的基準曲線縮放到 'frequency'
    ratio = frequency / base_f
    ratio_sq = ratio ** 2
    
    new_Q_curve = base_Q_calibrated * ratio
    new_H_curve = base_H_calibrated * ratio_sq
    
    # 4. 【內插法】反向查詢
    max_head = new_H_curve[0]
    min_head = new_H_curve[-1]
    
    if head >= max_head:
        return 0.0
    if head <= min_head:
        return new_Q_curve[-1]
        
    # [::-1] 是因為 H 遞減，Q 遞增，內插法需要 x 軸 (H) 遞增
    predicted_flow = np.interp(head, new_H_curve[::-1], new_Q_curve[::-1])
    
    return predicted_flow

# --- 2. 功耗模型 ---

def get_pump_power(pump_id, frequency, flow, head):
    """
    【您必須提供】您訓練好的 "功耗" 迴歸模型。
    輸入 (f, Q, H)，輸出 Power (kW)。
    (單位必須一致！ Q 是 m³/s)
    """
    # --- 範例 (請用您的迴歸公式替換) ---
    if flow <= 0 or frequency <= 0:
        return 0.0
        
    # 這是一個非常簡陋的物理估計 P = (Q * H * g * rho) / efficiency
    # 您的迴歸模型會更準確
    # P_kW = (Q_m3s * H_m * 9.81 * 1000) / (0.75 * 1000)
    # 假設效率 75%
    if flow > 0:
        power_kw = (flow * head * 9.81 * 1000) / (0.75 * 1000)
        return power_kw
    return 0.0
    # --- 範例結束 ---


# --- 3. 系統模擬器 (fsolve) ---

def get_system_head(total_flow_m3s, static_head):
    """
    系統曲線: H = H_static + k * Q^2
    """
    return static_head + SYSTEM_K_VALUE * (total_flow_m3s ** 2)

def simulate_hour(frequencies, static_head, degradation_factors):
    """
    模擬一小時的工況，找出(H_op, Q_op)和功耗。
    """
    
    # 這是 fsolve 要解的方程
    def equations_to_solve(head_guess):
        # head_guess 是一個純量 (e.g., [30.0])
        H = head_guess[0] 
        
        # 1. 系統需求 (需求曲線)
        if H < static_head:
            system_flow = 0.0
        else:
            system_flow = np.sqrt((H - static_head) / SYSTEM_K_VALUE)
        
        # 2. 抽水機供給 (供給曲線)
        pump_flow = 0.0
        for i in range(4): # 4 台泵
            pump_id = i + 1
            f = frequencies[i]
            pump_flow += get_pump_flow(pump_id, f, H, degradation_factors)
            
        # 求解目標： 供給 - 需求 = 0
        return pump_flow - system_flow

    # 3. 執行 fsolve 求解器
    #    (給一個合理的初始猜測值，例如 H_static + 5m)
    try:
        H_op = fsolve(equations_to_solve, [static_head + 5.0])[0]
    except Exception as e:
        # 求解失敗，可能是不合理的工況
        print(f"求解器失敗: {e} | freqs: {frequencies} | H_static: {static_head}")
        return 0.0, 0.0 # 回傳 0 功耗 0 流量

    # 4. 找到 H_op，計算該工況下的總流量和總功耗
    total_flow_op = 0.0
    total_power_op = 0.0
    
    for i in range(4):
        pump_id = i + 1
        f = frequencies[i]
        
        q_op = get_pump_flow(pump_id, f, H_op, degradation_factors)
        p_op = get_pump_power(pump_id, f, q_op, H_op)
        
        total_flow_op += q_op
        total_power_op += p_op
        
    # 回傳 (總功耗 kW, 總流量 m³/s)
    return total_power_op, total_flow_op