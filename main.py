import os
import time

def run_step(script_name):
    print(f"\n====== 正在執行 {script_name} ======")
    # 使用 os.system 呼叫 python 執行檔案
    exit_code = os.system(f"python {script_name}")
    
    if exit_code != 0:
        print(f"錯誤：{script_name} 執行失敗！流程終止。")
        return False
    return True

if __name__ == "__main__":
    start_time = time.time()

    # 1. 資料處理
    if not run_step("process_data.py"): exit()
    
    # 2. 系統校準
    if not run_step("calibrate.py"): exit()
    
    # 3. 最佳化計算
    if not run_step("optimize.py"): exit()

    end_time = time.time()
    print(f"\n====== 全部完成！總耗時: {end_time - start_time:.2f} 秒 ======")