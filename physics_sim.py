# physics_sim.py
import numpy as np
from scipy.optimize import fsolve
from config import PUMP_BASE_CURVES

def get_pump_flow(pump_id, frequency, head, degradation_factors):
    """
    計算單台抽水機在給定頻率(f)和揚程(H)下的流量(Q)。
    應用了相似定律 (Affinity Laws) 與老化因子。
    """
    if frequency <= 0.1: # 頻率趨近 0 則視為關機
        return 0.0
    
    # 1. 取得該泵的衰退因子 (預設為 1.0 無衰退)
    #    dH: 揚程衰退 (曲線上下縮放)
    #    dQ: 流量衰退 (曲線左右縮放)
    d_H = degradation_factors.get(f'pump{pump_id}_dH', 1.0)
    d_Q = degradation_factors.get(f'pump{pump_id}_dQ', 1.0)
    
    # 2. 讀取原廠 60Hz 曲線
    curve = PUMP_BASE_CURVES[f'pump{pump_id}']
    base_f = curve['freq']
    
    # 3. 先對原廠曲線進行 "老化縮放"
    base_H_cal = curve['head'] * d_H
    base_Q_cal = curve['flow'] * d_Q
    
    # 4. 再進行 "相似定律 (Affinity Laws)" 縮放
    #    Q_new = Q_base * (f_new / f_base)
    #    H_new = H_base * (f_new / f_base)^2
    ratio = frequency / base_f
    new_Q_curve = base_Q_cal * ratio
    new_H_curve = base_H_cal * (ratio ** 2)
    
    # 5. 使用內插法 (Interpolation) 查表
    #    給定現在的揚程 H (head)，反查能打出多少水 Q
    
    # 邊界檢查：如果揚程太高 (超過關死點)，流量為 0
    if head >= new_H_curve[0]: 
        return 0.0
    # 邊界檢查：如果揚程太低 (低於曲線範圍)，取最大流量
    if head <= new_H_curve[-1]: 
        return new_Q_curve[-1]
    
    # 內插 (注意：np.interp 需要 x 軸遞增，但 H 通常是遞減，所以用 [::-1] 反轉陣列)
    predicted_flow = np.interp(head, new_H_curve[::-1], new_Q_curve[::-1])
    
    return predicted_flow

def simulate_hour(freqs, static_head, factors, system_k):
    """
    模擬一小時的系統運作。
    
    輸入:
      freqs: [f1, f2, f3] 三台泵的頻率
      static_head: 靜揚程 (出水口高程 - 入水口水位)
      factors: 衰退因子字典
      system_k: 管損係數
      
    輸出:
      H_op: 平衡點揚程 (m)
      total_flow: 總流量 (m3/s)
      total_power: 總功耗 (kW) - 估算值
    """
    
    # 定義平衡方程式：供給流量 - 需求流量 = 0
    def equations(h_guess):
        H = h_guess[0]
        
        # 1. 系統需求曲線 (System Curve)
        #    Q_sys = sqrt((H - H_static) / K)
        if H < static_head:
            q_sys = 0.0
        else:
            q_sys = np.sqrt((H - static_head) / system_k)
        
        # 2. 抽水機供給曲線 (Pump Curve)
        #    Q_pump = Q1 + Q2 + Q3
        q_pump = 0.0
        for i in range(3):
            q_pump += get_pump_flow(i+1, freqs[i], H, factors)
            
        return q_pump - q_sys

    # 使用 fsolve 求解平衡揚程
    # 初始猜測值設為 靜揚程 + 10m
    try:
        H_op = fsolve(equations, [static_head + 10.0])[0]
    except:
        return 0.0, 0.0, 0.0 # 求解失敗
        
    # --- 計算結果 ---
    total_flow = 0.0
    total_power = 0.0
    
    for i in range(3):
        f = freqs[i]
        # 再次呼叫函數取得該泵在平衡揚程下的流量
        q = get_pump_flow(i+1, f, H_op, factors)
        total_flow += q
        
        # --- 功耗計算 ---
        # 這裡使用簡易物理公式 P = (rho * g * Q * H) / efficiency
        # 如果您有每台泵的 "功率迴歸公式"，請在這裡替換！
        if q > 0:
            # 假設綜合效率 (馬達+泵) 為 60% (0.6)
            # 1 kW = 1000 W
            # P (kW) = (Q(m3/s) * H(m) * 9810) / (0.6 * 1000)
            efficiency = 0.6 
            p = (q * H_op * 9.81) / efficiency
            total_power += p
            
    return H_op, total_flow, total_power