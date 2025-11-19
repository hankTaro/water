# process_data.py
import pandas as pd
import os
from config import RAW_DATA_PATH, PROCESSED_DATA_PATH

def process_data():
    print(f"正在讀取原始檔案: {RAW_DATA_PATH} ...")
    
    # 嘗試不同的編碼讀取 CSV (避免亂碼)
    try:
        df = pd.read_csv(RAW_DATA_PATH, header=2, encoding='cp950')
    except:
        try:
            df = pd.read_csv(RAW_DATA_PATH, header=2, encoding='big5')
        except:
            df = pd.read_csv(RAW_DATA_PATH, header=2, encoding='utf-8')

    # --- 提取關鍵欄位 ---
    # 根據您提供的檔案結構 (Index):
    # 1: f1, 4: P1
    # 7: f2, 10: P2
    # 13: f3, 16: P3
    # 25: Inlet_Level (取水口水位)
    # 28: Outlet_Pressure (出水壓力)
    # 29: Q_total (總流量 CMD)
    
    data = {
        'f1': df.iloc[:, 1],
        'P1_measured': df.iloc[:, 4],
        'f2': df.iloc[:, 7],
        'P2_measured': df.iloc[:, 10],
        'f3': df.iloc[:, 13],
        'P3_measured': df.iloc[:, 16],
        'Inlet_Level': df.iloc[:, 25],
        'Outlet_Pressure': df.iloc[:, 28], # 壓力 (單位依現場儀表)
        'Q_total_cmd': df.iloc[:, 29]      # 原始流量 (CMD)
    }
    
    df_out = pd.DataFrame(data)
    
    # --- 數據清洗 ---
    # 移除空值
    df_out.dropna(inplace=True)
    
    # 轉換為數值型別 (避免字串混入)
    for col in df_out.columns:
        df_out[col] = pd.to_numeric(df_out[col], errors='coerce')
    df_out.dropna(inplace=True)

    # --- 單位轉換 (關鍵步驟) ---
    # 1. 流量: CMD (m3/day) -> CMS (m3/s)
    #    1 天 = 86400 秒
    df_out['Q_total_m3s'] = df_out['Q_total_cmd'] / 86400.0
    
    # 2. 壓力: 假設 0.17 是 kg/cm2，大約等於 1.7m 水頭
    #    保留原始數據，讓校準程式去決定如何匹配
    
    # --- 儲存 ---
    os.makedirs('data', exist_ok=True)
    df_out.to_csv(PROCESSED_DATA_PATH, index=False)
    print(f"資料轉換完成！")
    print(f"總筆數: {len(df_out)}")
    print(f"已儲存至: {PROCESSED_DATA_PATH}")
    print(df_out.head())

if __name__ == "__main__":
    process_data()