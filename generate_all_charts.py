#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 圖表批量生成腳本
用於本地測試或手動生成所有 ETF 配置的分析圖表
"""

import os
import sys
import subprocess
from datetime import datetime
import shutil

def run_etf_analysis(config_type):
    """運行單個 ETF 配置的分析"""
    print(f"\n{'='*60}")
    print(f"🔄 開始生成 {config_type} 的圖表...")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            [sys.executable, 'ETFEngine_main.py', config_type],
            capture_output=False,
            timeout=600  # 10 分鐘超時
        )
        
        if result.returncode == 0:
            print(f"✅ {config_type} 圖表生成成功")
            
            # 自動添加時間戳到生成的 PNG 文件
            print(f"  📌 添加時間戳到 PNG 文件...")
            folder_mapping = {
                'active_etf': 'Output_Active_ETF',
                'high_dividend_etf': 'Output_HighDividend_ETF',
                'industry_etf': 'Output_Industry_ETF',
                'us_etf': 'Output_US_ETF',
                'dividend_etf': 'Output_Dividend_ETF'
            }
            
            output_folder = folder_mapping.get(config_type, 'Output_Default')
            if os.path.exists(output_folder):
                try:
                    subprocess.run(
                        [sys.executable, 'add_timestamps.py', output_folder],
                        capture_output=True,
                        timeout=60
                    )
                    print(f"  ✅ 時間戳添加完成")
                except Exception as e:
                    print(f"  ⚠️  時間戳添加失敗: {e}")
            
            return True
        else:
            print(f"⚠️  {config_type} 圖表生成失敗（代碼 {result.returncode}）")
            return False
    except subprocess.TimeoutExpired:
        print(f"❌ {config_type} 生成超時（超過 10 分鐘）")
        return False
    except Exception as e:
        print(f"❌ {config_type} 生成出錯: {e}")
        return False


def collect_outputs():
    """收集所有生成的圖表到 charts_output 文件夾"""
    print(f"\n{'='*60}")
    print("📦 收集所有輸出文件...")
    print(f"{'='*60}")
    
    output_dir = 'charts_output'
    
    # 創建或清空輸出目錄
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)
    
    # 複製所有 Output_*_ETF 文件夾中的文件
    total_files = 0
    for folder in os.listdir('.'):
        if folder.startswith('Output_') and folder.endswith('_ETF'):
            png_count = 0
            csv_count = 0
            
            folder_path = os.path.join(folder)
            
            # 複製 PNG 文件
            for file in os.listdir(folder_path):
                if file.endswith('.png'):
                    src = os.path.join(folder_path, file)
                    dst = os.path.join(output_dir, f"{folder}_{file}")
                    shutil.copy2(src, dst)
                    png_count += 1
                    total_files += 1
                
                elif file.endswith('.csv'):
                    src = os.path.join(folder_path, file)
                    dst = os.path.join(output_dir, f"{folder}_{file}")
                    shutil.copy2(src, dst)
                    csv_count += 1
                    total_files += 1
            
            print(f"  ✅ {folder}: {png_count} PNG + {csv_count} CSV")
    
    print(f"\n📊 共收集 {total_files} 個文件到 {output_dir}/")
    return output_dir


def print_summary(results):
    """打印生成摘要"""
    print(f"\n{'='*60}")
    print("📋 生成摘要")
    print(f"{'='*60}")
    
    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    
    print(f"\n成功: {success_count}/{total_count}")
    for config, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {config}")
    
    print(f"\n生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success_count == total_count:
        print("\n🎉 所有圖表已成功生成！")
    else:
        print(f"\n⚠️  有 {total_count - success_count} 個配置生成失敗")


def main():
    """主函數"""
    print(f"{'='*60}")
    print("🚀 ETF 圖表批量生成工具")
    print(f"{'='*60}")
    print(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 支持的 ETF 配置
    configs = [
        'active_etf',
        'high_dividend_etf',
        'industry_etf'
    ]
    
    # 允許通過命令行參數指定要生成的配置
    if len(sys.argv) > 1:
        configs = sys.argv[1:]
        print(f"📌 指定生成: {', '.join(configs)}")
    else:
        print(f"📌 將生成所有配置: {', '.join(configs)}")
    
    print()
    
    # 運行分析
    results = {}
    for config in configs:
        results[config] = run_etf_analysis(config)
    
    # 收集輸出
    output_dir = collect_outputs()
    
    # 打印摘要
    print_summary(results)
    
    # 列出生成的文件
    print(f"\n📁 生成的文件:")
    if os.path.exists(output_dir):
        files = os.listdir(output_dir)
        for file in sorted(files):
            size = os.path.getsize(os.path.join(output_dir, file))
            size_str = f"{size/1024/1024:.2f}MB" if size > 1024*1024 else f"{size/1024:.2f}KB"
            print(f"  • {file} ({size_str})")
    
    print(f"\n✅ 生成完成！輸出位置: {os.path.abspath(output_dir)}/")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  用戶中斷生成")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")
        sys.exit(1)
