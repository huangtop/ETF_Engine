#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 圖表生成模組
包含所有繪圖函數，從主程式分離出來以便重用和維護
"""

import os
import sys
import subprocess
from datetime import datetime, timedelta
import shutil
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from math import pi
from config_loader import load_etf_config
from data_fetcher import download_price_data
from add_timestamp_to_titles import add_timestamps_to_all_charts

# Font size config
FONT_SIZE_CONFIG = {
    'title_large': 27,        # 大标题: 18 * 1.5
    'title_medium': 21,       # 中标题: 14 * 1.5
    'title_small': 18,        # 小标题: 12 * 1.5
    
    'label_large': 18,        # 大标签: 12 * 1.5
    'label_medium': 15,       # 中标签: 10 * 1.5
    'label_small': 13,        # 小标签: 8.5 * 1.5
    
    'tick_large': 16,         # 大刻度: ~10.5 * 1.5
    'tick_medium': 13,        # 中刻度: ~8.5 * 1.5
    'tick_small': 11,         # 小刻度: 7.5 * 1.5
    
    'legend': 26,             # 图例: 13 * 2（加大一倍）
    'figure_text': 12,        # 图表说明文字
}

# 全局基準數據快取 - 避免重複下載美股基準數據
_benchmark_cache = {}

# 🚀 基準數據文件快取 - 跨ETF類型、跨執行持久化
import json
import os
from datetime import datetime, timedelta

BENCHMARK_CACHE_DIR = 'cache'
BENCHMARK_CACHE_FILE = os.path.join(BENCHMARK_CACHE_DIR, 'benchmark_cache.json')
BENCHMARK_CACHE_VALIDITY_HOURS = 12  # 基準數據快取12小時

def _ensure_benchmark_cache_dir():
    """確保基準快取目錄存在"""
    if not os.path.exists(BENCHMARK_CACHE_DIR):
        os.makedirs(BENCHMARK_CACHE_DIR)

def _load_benchmark_cache():
    """從檔案讀取基準數據快取"""
    if os.path.exists(BENCHMARK_CACHE_FILE):
        try:
            with open(BENCHMARK_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 基準快取讀取失敗: {e}")
    return {}

def _save_benchmark_cache(cache):
    """將基準數據快取寫入檔案"""
    try:
        _ensure_benchmark_cache_dir()
        with open(BENCHMARK_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ 基準快取保存失敗: {e}")

def _is_benchmark_cache_valid(cached_item):
    """檢查基準快取是否仍有效（12小時內）"""
    if 'timestamp' not in cached_item:
        return False
    
    try:
        cached_time = datetime.fromisoformat(cached_item['timestamp'])
        now = datetime.now()
        hours_old = (now - cached_time).total_seconds() / 3600
        return hours_old < BENCHMARK_CACHE_VALIDITY_HOURS
    except:
        return False

def get_benchmark_data(symbol, start_date, end_date, name=None):
    """
    獲取基準數據（支持跨ETF類型、跨程序執行的持久化快取）
    
    遠端執行時，三種ETF類型依次執行：
    1. 主動式ETF → 嘗試下載基準數據 → 保存成功/失敗狀態到文件快取
    2. 高股息ETF → 檢查快取狀態，如果失敗則直接跳過 ⚡
    3. 產業型ETF → 檢查快取狀態，如果失敗則直接跳過 ⚡
    
    Args:
        symbol: 基準代碼 (如 '^GSPC', 'VOO', '0050.TW')
        start_date: 開始日期
        end_date: 結束日期  
        name: 顯示名稱（可選）
    
    Returns:
        pd.Series or pd.DataFrame: 價格數據，失敗時返回 None
    """
    cache_key = f"{symbol}_{start_date}_{end_date}"
    display_name = name or symbol
    
    # 🚀 優先檢查文件快取（跨程序執行持久化）
    file_cache = _load_benchmark_cache()
    if cache_key in file_cache and _is_benchmark_cache_valid(file_cache[cache_key]):
        cached_item = file_cache[cache_key]
        
        # 檢查是否為失敗記錄
        if cached_item.get('status') == 'failed':
            print(f"� 從快取得知之前失敗: {display_name} ({symbol}) - 跳過重新下載")
            _benchmark_cache[cache_key] = None  # 同時更新內存快取
            return None
            
        # 成功記錄，恢復數據
        if cached_item.get('status') == 'success':
            print(f"�📁 從文件快取復用: {display_name} ({symbol})")
            try:
                cached_data = cached_item['data']
                # 重建 pandas Series
                if isinstance(cached_data, dict) and 'index' in cached_data and 'values' in cached_data:
                    prices = pd.Series(
                        data=cached_data['values'], 
                        index=pd.to_datetime(cached_data['index'])
                    )
                    _benchmark_cache[cache_key] = prices  # 同時更新內存快取
                    return prices
            except Exception as e:
                print(f"⚠️ 文件快取恢復失敗: {e}")
    
    if cache_key not in _benchmark_cache:
        print(f"📥 下載基準數據: {display_name} ({symbol})")
        try:
            from data_fetcher import download_price_data
            data = download_price_data(symbol, start_date=start_date, end_date=end_date)
            if not data.empty:
                # 統一返回 Close 價格序列
                if isinstance(data, pd.DataFrame) and 'Close' in data.columns:
                    prices = data['Close']
                    if isinstance(prices, pd.DataFrame):
                        prices = prices.iloc[:, 0]
                    _benchmark_cache[cache_key] = prices
                else:
                    _benchmark_cache[cache_key] = data
                    prices = data
                    
                print(f"✅ {display_name} 基準數據已快取 ({len(_benchmark_cache[cache_key])} 天)")
                
                # 🚀 保存成功狀態到文件快取
                try:
                    file_cache[cache_key] = {
                        'timestamp': datetime.now().isoformat(),
                        'symbol': symbol,
                        'name': display_name,
                        'status': 'success',
                        'data': {
                            'index': prices.index.astype(str).tolist(),
                            'values': prices.values.tolist()
                        }
                    }
                    _save_benchmark_cache(file_cache)
                    print(f"💾 {display_name} 成功狀態已保存到文件快取")
                except Exception as e:
                    print(f"⚠️ 文件快取保存失敗: {e}")
                    
            else:
                _benchmark_cache[cache_key] = None
                print(f"❌ {display_name} 數據為空")
                
                # 🚀 保存失敗狀態到文件快取
                try:
                    file_cache[cache_key] = {
                        'timestamp': datetime.now().isoformat(),
                        'symbol': symbol,
                        'name': display_name,
                        'status': 'failed',
                        'error': 'empty_data'
                    }
                    _save_benchmark_cache(file_cache)
                    print(f"💾 {display_name} 失敗狀態已保存到快取，後續ETF類型將跳過")
                except Exception as e:
                    print(f"⚠️ 失敗狀態快取保存失敗: {e}")
                    
        except Exception as e:
            print(f"❌ {display_name} 下載失敗: {e}")
            _benchmark_cache[cache_key] = None
            
            # 🚀 保存失敗狀態到文件快取
            try:
                file_cache[cache_key] = {
                    'timestamp': datetime.now().isoformat(),
                    'symbol': symbol,
                    'name': display_name,
                    'status': 'failed',
                    'error': str(e)
                }
                _save_benchmark_cache(file_cache)
                print(f"💾 {display_name} 失敗狀態已保存到快取，後續ETF類型將跳過")
            except Exception as cache_e:
                print(f"⚠️ 失敗狀態快取保存失敗: {cache_e}")
    else:
        print(f"💾 復用內存快取: {display_name} ({symbol})")
    
    return _benchmark_cache[cache_key]

def generate_chart_title_with_timestamp(base_title):
    """生成帶有時間戳的圖表標題"""
    from datetime import datetime
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    return f"{base_title} ({current_time} 生成)"

def setup_matplotlib_backend():
    """設定 matplotlib 後端並返回 pyplot（優化版本）"""
    import matplotlib
    matplotlib.use('Agg', force=True)
    import matplotlib.pyplot as plt
    plt.ioff()
    
    # 優化渲染設置
    plt.rcParams['figure.max_open_warning'] = 0  # 關閉過多圖表警告
    plt.rcParams['agg.path.chunksize'] = 10000   # 優化路徑渲染
    
    return plt

def setup_chinese_font():
    """設置中文字體 - 修復版本"""
    try:
        # 設定中文字體為優先
        plt.rcParams['font.family'] = ['sans-serif']
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'Noto Sans CJK TC', 'Noto Sans CJK SC', 'WenQuanYi Zen Hei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        print("✅ 中文字體設定完成")
        
    except Exception as e:
        print(f"⚠️ 中文字體設定失敗: {e}")
        # 備用設定
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei']
        plt.rcParams['axes.unicode_minus'] = False

def plot_turnover_bar(df_results):
    """繪製換手率條形圖（Chart.js 格式）"""
    labels = df_results['名稱'].tolist()
    turnover = [float(x) if x != 'N/A' else 0 for x in df_results['換手率 (%)']]
    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "換手率 (%)",
                "data": turnover,
                "backgroundColor": ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40", "#C9CBCF", "#7BC225", "#FF5733", "#C70039", "#900C3F"],
                "borderColor": ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40", "#C9CBCF", "#7BC225", "#FF5733", "#C70039", "#900C3F"],
                "borderWidth": 1
            }]
        },
        "options": {
            "scales": {
                "y": {
                    "beginAtZero": True,
                    "title": {"display": True, "text": "換手率 (%)"}
                },
                "x": {
                    "title": {"display": True, "text": "ETF 名稱"}
                }
            },
            "plugins": {
                "legend": {"display": False},
                "title": {"display": True, "text": "ETF 換手率比較"}
            }
        }
    }


def plot_radar_chart(df_results, config=None, etf_type_prefix="", output_folder="."):
    """繪製多指標雷達圖（分類拆分，使用不同標記）
    
    Args:
        df_results: ETF 分析結果 DataFrame
        etf_type_prefix: ETF 類型前綴（如 "Active_", "HighDividend_", "Industry_"）
    """
    from math import pi
    import os
    
    plt = setup_matplotlib_backend()
    setup_chinese_font()
    
    categories = ['1年年化報酬率', '夏普比率', '波動率(反)', '最大回撤(反)', '追蹤誤差(反)']
    categories_en = ['1Y Return', 'Sharpe', 'Low Volatility', 'Low Max DD', 'Low Tracking Error']
    
    N = len(categories)
    angles = [n / float(N) * 2 * pi for n in range(N)]
    angles += angles[:1]
    
    # 分類ETF資料（從 JSON 配置讀取）
    us_etfs = []
    tw_stock_etfs = []
    tw_dividend_etfs = []
    
    for _, row in df_results.iterrows():
        # 🔧 檢查數據天數，排除不可靠的數據
        data_days = row.get('數據天數', 0)
        if data_days < 30:  # 數據不足30天，跳過分類
            print(f"⚠️  雷達圖排除 {row['證券代碼']} - 數據不足 ({data_days} 天 < 30天)")
            continue
            
        ticker = row['證券代碼'].strip()
        name = row['名稱'].strip()
        
        # 🔧 從config的etf_list中查找type（不是etf_type）
        etf_type = None
        if config and 'etf_list' in config:
            for etf in config['etf_list']:
                if etf.get('ticker') == ticker:
                    etf_type = etf.get('type')
                    break
        
        if etf_type == 'us':
            us_etfs.append(row)
        elif etf_type == 'dividend':
            tw_dividend_etfs.append(row)
        else:
            # 預設為台股股票型（包含 tw_active 和其他台股ETF）
            tw_stock_etfs.append(row)
    
    # 收集數據範圍（雷達圖強制使用1年數據，但排除數據不足的ETF）
    all_returns, all_sharpe, all_vol, all_dd, all_te = [], [], [], [], []
    
    for _, row in df_results.iterrows():
        # 🔧 檢查數據天數，排除不可靠的數據
        data_days = row.get('數據天數', 0)
        if data_days < 30:  # 數據不足30天，跳過
            print(f"⚠️  雷達圖排除 {row['證券代碼']} - 數據不足 ({data_days} 天 < 30天)")
            continue
            
        # 使用1年年化報酬率
        ret_val = row.get('1年年化報酬率 (%)', 'N/A')
        if ret_val != 'N/A' and ret_val != 9999:
            all_returns.append(float(ret_val))
            
        # 其他指標：使用1年版本
        if row['1年夏普比率'] != 'N/A':
            all_sharpe.append(float(row['1年夏普比率']))
        if row['1年年化波動率 (%)'] != 'N/A':
            all_vol.append(float(row['1年年化波動率 (%)']))
        if row['1年最大回撤 (%)'] != 'N/A':
            # 最大回撤取絕對值後再加入範圍計算
            all_dd.append(abs(float(row['1年最大回撤 (%)'])))
        if row['1年追蹤誤差 (%)'] != 'N/A':
            all_te.append(float(row['1年追蹤誤差 (%)']))
    
    # 計算範圍
    return_min, return_max = (min(all_returns), max(all_returns)) if all_returns else (0, 1)
    sharpe_min, sharpe_max = (min(all_sharpe), max(all_sharpe)) if all_sharpe else (0, 1)
    vol_min, vol_max = (min(all_vol), max(all_vol)) if all_vol else (0, 1)
    dd_min, dd_max = (min(all_dd), max(all_dd)) if all_dd else (0, 1)
    te_min, te_max = (min(all_te), max(all_te)) if all_te else (0, 1)
    
    def normalize_value(value, min_val, max_val, reverse=False):
        if min_val == max_val:
            return 50
        normalized = ((value - min_val) / (max_val - min_val)) * 100
        if reverse:
            normalized = 100 - normalized
        return max(0, min(100, normalized))
    
    def plot_single_radar(etf_data, title, filename, colors, markers, linestyles, etf_type_prefix=""):
        """繪製單一雷達圖"""
        fig, ax = plt.subplots(figsize=(12, 12), subplot_kw=dict(polar=True))
        
        for i, row in enumerate(etf_data):
            ticker = row['證券代碼'].strip()
            name = row['名稱'].strip()
            short_name = row.get('短名稱', name).strip()
            
            # 使用短名稱
            display_name = f"{ticker.replace('.TW', '')}\n{short_name}".replace('\n', ' ')
            
            # 計算標準化數值（使用1年年化報酬率，排除9999異常值）
            values = []
            ret_val = row.get('1年年化報酬率 (%)', 'N/A')
            if ret_val != 'N/A' and ret_val != 9999:
                ret_val = float(ret_val)
            else:
                ret_val = return_min  # 使用最小值作為預設
            values.append(normalize_value(ret_val, return_min, return_max, reverse=False))
            
            sharpe_val = float(row['1年夏普比率']) if row['1年夏普比率'] != 'N/A' else sharpe_min
            values.append(normalize_value(sharpe_val, sharpe_min, sharpe_max, reverse=False))
            
            vol_val = float(row['1年年化波動率 (%)']) if row['1年年化波動率 (%)'] != 'N/A' else vol_max
            values.append(normalize_value(vol_val, vol_min, vol_max, reverse=True))
            
            # 最大回撤取絕對值
            dd_val = float(row['1年最大回撤 (%)']) if row['1年最大回撤 (%)'] != 'N/A' else dd_min
            if dd_val < 0:
                dd_val = abs(dd_val)
            values.append(normalize_value(dd_val, dd_min, dd_max, reverse=True))
            
            te_val = float(row['1年追蹤誤差 (%)']) if row['1年追蹤誤差 (%)'] != 'N/A' else te_max
            values.append(normalize_value(te_val, te_min, te_max, reverse=True))
            
            values += values[:1]  # 閉合圖形
            
            # 取得顏色和標記
            color = colors[i % len(colors)]
            marker = markers[i % len(markers)]
            linestyle = linestyles[i % len(linestyles)]
            
            # 繪製線條
            ax.plot(angles, values, linewidth=3, linestyle=linestyle, 
                    label=display_name, color=color, alpha=0.8)
            ax.fill(angles, values, alpha=0.15, color=color)
            
            # 使用不同標記增加識別度
            ax.scatter(angles[:-1], values[:-1], color=color, s=80, 
                      marker=marker, alpha=0.9, zorder=5, edgecolors='black', linewidth=1)
        
        # 設定標籤和標題
        ax.set_xticks(angles[:-1])
        try:
            ax.set_xticklabels(categories, fontsize=14, fontweight='bold')
        except:
            ax.set_xticklabels(categories_en, fontsize=14, fontweight='bold')
        
        ax.set_title(generate_chart_title_with_timestamp(title), fontsize=18, pad=40, fontweight='bold')
        ax.set_ylim(0, 100)
        ax.set_yticks([20, 40, 60, 80, 100])
        ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=12)
        ax.grid(True, alpha=0.4)
        
        # 添加同心圓標籤
        ax.text(0, 110, '100', ha='center', va='center', fontsize=12, alpha=0.7, fontweight='bold')
        ax.text(0, 90, '80', ha='center', va='center', fontsize=12, alpha=0.7)
        ax.text(0, 70, '60', ha='center', va='center', fontsize=12, alpha=0.7)
        
        # 圖例
        legend = plt.legend(bbox_to_anchor=(1.15, 1.0), loc='upper left', 
                           fontsize=14, frameon=True, fancybox=True, shadow=True,
                           title='ETF 清單', title_fontsize=16)
        
        plt.tight_layout()
        
        # 儲存圖片到輸出資料夾
        try:
            output_path = os.path.join(output_folder, f'{etf_type_prefix}{filename}')
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"✅ {title}已儲存為: {output_path}")
        except Exception as e:
            try:
                output_path = os.path.join(output_folder, filename)
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                print(f"✅ {title}已儲存為: {output_path}")
            except:
                print(f"❌ {title}儲存失敗: {e}")
        
        plt.close()
    
    # 1. 美股相關ETF雷達圖 - 擴展顏色和線條以支援多達30支ETF
    if us_etfs:
        us_colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
            '#DFE6E9', '#A29BFE', '#6C5CE7', '#74B9FF', '#81ECEC',
            '#55EFC4', '#FD79A8', '#FDCB6E', '#6C7A89', '#00B894',
            '#FF7675', '#74B9FF', '#A29BFE', '#00CEC9', '#FF6348',
            '#F39C12', '#E74C3C', '#3498DB', '#2ECC71', '#9B59B6',
            '#1ABC9C', '#34495E', '#C0392B', '#16A085', '#D35400'
        ]
        us_linestyles = ['-', '--', '-.', ':', '-', '--', '-.', ':', '-', '--',
                         '-.', ':', '-', '--', '-.', ':', '-', '--', '-.', ':',
                         '-', '--', '-.', ':', '-', '--', '-.', ':', '-', '--']
        us_markers = ['^'] * len(us_colors)
        
        plot_single_radar(us_etfs, 
                         '美股相關ETF雷達圖\n△ 三角形標記', 
                         'radar_us_etfs.png',
                         us_colors, us_markers, us_linestyles, etf_type_prefix)
    
    # 2. 台股股票型ETF雷達圖 - 擴展顏色和線條以支援多達30支ETF
    if tw_stock_etfs:
        stock_colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
            '#DFE6E9', '#A29BFE', '#6C5CE7', '#74B9FF', '#81ECEC',
            '#55EFC4', '#FD79A8', '#FDCB6E', '#6C7A89', '#00B894',
            '#FF7675', '#74B9FF', '#A29BFE', '#00CEC9', '#FF6348',
            '#F39C12', '#E74C3C', '#3498DB', '#2ECC71', '#9B59B6',
            '#1ABC9C', '#34495E', '#C0392B', '#16A085', '#D35400'
        ]
        stock_linestyles = ['-', '--', '-.', ':', '-', '--', '-.', ':', '-', '--',
                            '-.', ':', '-', '--', '-.', ':', '-', '--', '-.', ':',
                            '-', '--', '-.', ':', '-', '--', '-.', ':', '-', '--']
        stock_markers = ['o'] * len(stock_colors)
        
        plot_single_radar(tw_stock_etfs, 
                         '台股股票型ETF雷達圖\n● 圓形標記', 
                         'radar_tw_stock.png',
                         stock_colors, stock_markers, stock_linestyles, etf_type_prefix)
    
    # 3. 台股高股息ETF雷達圖 - 擴展顏色和線條以支援多達30支ETF
    if tw_dividend_etfs:
        div_colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
            '#DFE6E9', '#A29BFE', '#6C5CE7', '#74B9FF', '#81ECEC',
            '#55EFC4', '#FD79A8', '#FDCB6E', '#6C7A89', '#00B894',
            '#FF7675', '#74B9FF', '#A29BFE', '#00CEC9', '#FF6348',
            '#F39C12', '#E74C3C', '#3498DB', '#2ECC71', '#9B59B6',
            '#1ABC9C', '#34495E', '#C0392B', '#16A085', '#D35400'
        ]
        div_linestyles = ['-', '--', '-.', ':', '-', '--', '-.', ':', '-', '--',
                          '-.', ':', '-', '--', '-.', ':', '-', '--', '-.', ':',
                          '-', '--', '-.', ':', '-', '--', '-.', ':', '-', '--']
        div_markers = ['s'] * len(div_colors)
        
        plot_single_radar(tw_dividend_etfs, 
                         '台股高股息ETF雷達圖\n■ 方形標記', 
                         'radar_tw_dividend.png',
                         div_colors, div_markers, div_linestyles, etf_type_prefix)
    
    # 4. 總覽雷達圖（所有ETF）
    fig, ax = plt.subplots(figsize=(16, 16), subplot_kw=dict(polar=True))
    
    # 定義標記映射
    marker_map = {
        'us': '^',      # 三角形 - 美股
        'stock': 'o',   # 圓形 - 台股股票型
        'dividend': 's' # 方形 - 台股高股息型
    }
    
    # 擴展顏色映射以支援更多ETF
    extended_colors = [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
        '#DFE6E9', '#A29BFE', '#6C5CE7', '#74B9FF', '#81ECEC',
        '#55EFC4', '#FD79A8', '#FDCB6E', '#6C7A89', '#00B894',
        '#FF7675', '#74B9FF', '#A29BFE', '#00CEC9', '#FF6348',
        '#F39C12', '#E74C3C', '#3498DB', '#2ECC71', '#9B59B6',
        '#1ABC9C', '#34495E', '#C0392B', '#16A085', '#D35400'
    ]
    extended_linestyles = ['-', '--', '-.', ':', '-', '--', '-.', ':', '-', '--',
                          '-.', ':', '-', '--', '-.', ':', '-', '--', '-.', ':',
                          '-', '--', '-.', ':', '-', '--', '-.', ':', '-', '--']
    
    color_map = {
        'us': extended_colors,
        'stock': extended_colors,
        'dividend': extended_colors
    }
    
    linestyle_map = {
        'us': extended_linestyles,
        'stock': extended_linestyles,
        'dividend': extended_linestyles
    }
    
    all_etf_data = []
    all_etf_data.extend([(row, 'us', i) for i, row in enumerate(us_etfs)])
    all_etf_data.extend([(row, 'stock', i) for i, row in enumerate(tw_stock_etfs)])
    all_etf_data.extend([(row, 'dividend', i) for i, row in enumerate(tw_dividend_etfs)])
    
    for row, etf_type, type_index in all_etf_data:
        ticker = row['證券代碼'].strip()
        name = row['名稱'].strip()
        short_name = row.get('短名稱', name).strip()
        
        # 使用短名稱（總覽圖用更簡潔版本）
        display_name = f"{ticker.replace('.TW', '')} {short_name}"
        
        # 計算標準化數值（使用1年年化報酬率）
        values = []
        ret_val = float(row.get('1年年化報酬率 (%)', 'N/A')) if row.get('1年年化報酬率 (%)', 'N/A') != 'N/A' else return_min
        values.append(normalize_value(ret_val, return_min, return_max, reverse=False))
        
        sharpe_val = float(row['1年夏普比率']) if row['1年夏普比率'] != 'N/A' else sharpe_min
        values.append(normalize_value(sharpe_val, sharpe_min, sharpe_max, reverse=False))
        
        vol_val = float(row['1年年化波動率 (%)']) if row['1年年化波動率 (%)'] != 'N/A' else vol_max
        values.append(normalize_value(vol_val, vol_min, vol_max, reverse=True))
        
        # 最大回撤取絕對值
        dd_val = float(row['1年最大回撤 (%)']) if row['1年最大回撤 (%)'] != 'N/A' else dd_min
        if dd_val < 0:
            dd_val = abs(dd_val)
        values.append(normalize_value(dd_val, dd_min, dd_max, reverse=True))
        
        te_val = float(row['1年追蹤誤差 (%)']) if row['1年追蹤誤差 (%)'] != 'N/A' else te_max
        values.append(normalize_value(te_val, te_min, te_max, reverse=True))
        
        values += values[:1]  # 閉合圖形
        
        # 取得顏色、標記和線型
        color = color_map[etf_type][type_index % len(color_map[etf_type])]
        marker = marker_map[etf_type]
        linestyle = linestyle_map[etf_type][type_index % len(linestyle_map[etf_type])]
        
        # 繪製線條
        ax.plot(angles, values, linewidth=2.5, linestyle=linestyle, 
                label=display_name, color=color, alpha=0.7)
        ax.fill(angles, values, alpha=0.1, color=color)
        
        # 使用不同標記增加識別度
        ax.scatter(angles[:-1], values[:-1], color=color, s=60, 
                  marker=marker, alpha=0.9, zorder=5, edgecolors='black', linewidth=1)
    
    # 設定標籤和標題
    ax.set_xticks(angles[:-1])
    try:
        ax.set_xticklabels(categories, fontsize=13, fontweight='bold')
        title = 'ETF 總覽雷達圖\n△美股相關 ●台股股票型 ■台股高股息型'
    except:
        ax.set_xticklabels(categories_en, fontsize=13, fontweight='bold')
        title = 'ETF Overview Radar Chart\n△US-Related ●TW-Stock ■TW-Dividend'
    
    ax.set_title(generate_chart_title_with_timestamp(title), fontsize=18, pad=40, fontweight='bold')
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=10)
    ax.grid(True, alpha=0.4)
    
    # 添加同心圓標籤
    ax.text(0, 110, '100', ha='center', va='center', fontsize=10, alpha=0.7)
    ax.text(0, 90, '80', ha='center', va='center', fontsize=10, alpha=0.7)
    ax.text(0, 70, '60', ha='center', va='center', fontsize=10, alpha=0.7)
    
    # 分兩列顯示圖例
    handles, labels = ax.get_legend_handles_labels()
    
    # 計算每列顯示的項目數
    n_items = len(labels)
    # 調整為多列顯示，避免超出圖表
    n_cols = 3  # 改為3列
    n_rows = (n_items + n_cols - 1) // n_cols
    
    # 合併所有 ETF 清單，不分 (1) 和 (2)，放在圖表右邊
    legend1 = plt.legend(handles, labels, 
                        bbox_to_anchor=(1.05, 1.0), loc='upper right', 
                        fontsize=13, frameon=True, fancybox=True, shadow=True,
                        title='ETF 清單', title_fontsize=15, ncol=1)
    
    # 移除標記說明，直接保存圖例
    plt.gca().add_artist(legend1)
    
    # 添加各指標冠軍信息
    print(f"\n🏆 各指標冠軍:")
    champion_info = []
    
    # 計算冠軍（雷達圖使用1年指標，所以冠軍也用1年）
    metrics_data = {
        '年化報酬率': ([], '1年年化報酬率 (%)'),
        '夏普比率': ([], '1年夏普比率'),
        '低波動': ([], '1年年化波動率 (%)'),
        '低回撤': ([], '1年最大回撤 (%)'),
        '低追蹤誤差': ([], '1年追蹤誤差 (%)'),
    }
    
    for _, row in df_results.iterrows():
        try:
            # 使用1年版本的指標計算冠軍
            ret_1y = row.get('1年年化報酬率 (%)', 'N/A')
            if ret_1y != 'N/A' and ret_1y != 9999:
                metrics_data['年化報酬率'][0].append((float(ret_1y), row['名稱'].strip(), row['證券代碼'].strip()))
            
            if row['1年夏普比率'] != 'N/A':
                metrics_data['夏普比率'][0].append((float(row['1年夏普比率']), row['名稱'].strip(), row['證券代碼'].strip()))
            if row['1年年化波動率 (%)'] != 'N/A':
                metrics_data['低波動'][0].append((float(row['1年年化波動率 (%)']), row['名稱'].strip(), row['證券代碼'].strip()))
            if row['1年最大回撤 (%)'] != 'N/A':
                metrics_data['低回撤'][0].append((float(row['1年最大回撤 (%)']), row['名稱'].strip(), row['證券代碼'].strip()))
            if row['1年追蹤誤差 (%)'] != 'N/A':
                metrics_data['低追蹤誤差'][0].append((float(row['1年追蹤誤差 (%)']), row['名稱'].strip(), row['證券代碼'].strip()))
        except (ValueError, KeyError):
            pass
    
    # 找出冠軍
    for metric_name, (data, _) in metrics_data.items():
        if data:
            if '低' in metric_name:
                # 低的指標取最小值
                champion = min(data, key=lambda x: x[0])
                champion_info.append(f"  🏆 {metric_name}: {champion[2]} ({champion[1]}) = {champion[0]:.2f}")
            else:
                # 高的指標取最大值
                champion = max(data, key=lambda x: x[0])
                champion_info.append(f"  🏆 {metric_name}: {champion[2]} ({champion[1]}) = {champion[0]:.2f}")
    
    # 打印冠軍信息
    for info in champion_info:
        print(info)
    
    # 在圖表上添加冠軍信息文本（放大一倍，靠左對齐）
    champion_text = '\n'.join([info.replace('  🏆 ', '') for info in champion_info])
    fig.text(0.02, -0.05, f'各指標冠軍:\n{champion_text}', 
             ha='left', fontsize=FONT_SIZE_CONFIG['label_medium'] * 2, 
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    
    plt.tight_layout()
    
    # 儲存總覽圖到輸出資料夾
    try:
        output_path = os.path.join(output_folder, f'{etf_type_prefix}radar_overview.png')
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"\n✅ 總覽雷達圖已儲存為: {output_path}")
    except Exception as e:
        try:
            output_path = os.path.join(output_folder, f'{etf_type_prefix}radar_overview.png')
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"✅ 總覽雷達圖已儲存為: {output_path}")
        except:
            print(f"❌ 總覽雷達圖儲存失敗: {e}")
    
    plt.close()
    
    # 輸出分類摘要
    print(f"\n📊 雷達圖分類摘要:")
    print(f"  △ 美股相關ETF: {len(us_etfs)} 支")
    print(f"  ● 台股股票型ETF: {len(tw_stock_etfs)} 支")
    print(f"  ■ 台股高股息ETF: {len(tw_dividend_etfs)} 支")
    print(f"  總計: {len(us_etfs) + len(tw_stock_etfs) + len(tw_dividend_etfs)} 支")

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

# New function for performance chart generation
def generate_performance_chart(df_results, ret_1y_dict, ret_3y_dict, benchmark_data, etf_type_prefix, output_folder):
    """Generate 2-column performance chart (1-year blue, 3-year yellow)"""
    import matplotlib.pyplot as plt
    import numpy as np
    
    plt.switch_backend('Agg')
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    
    print("\n�� Generating performance chart...")
    
    try:
        # Split Taiwan vs US ETFs
        taiwan_etfs = []
        us_etfs = []
        
        for _, row in df_results.iterrows():
            ticker = row['證券代碼'].strip()
            name = row['名稱'].strip()
            ret_1y = ret_1y_dict.get(ticker, 9999)
            ret_3y = ret_3y_dict.get(ticker, 9999)
            
            # 9999 becomes 0 (don't show)
            ret_1y = ret_1y if ret_1y != 9999 else 0
            ret_3y = ret_3y if ret_3y != 9999 else 0
            
            if '美股' in name or 'US' in name or any(code in ticker for code in ['00646', '00662', '00757', '00983A', '00988A', '00989A']):
                us_etfs.append({'ticker': ticker, 'name': name, 'ret_1y': ret_1y, 'ret_3y': ret_3y})
            else:
                taiwan_etfs.append({'ticker': ticker, 'name': name, 'ret_1y': ret_1y, 'ret_3y': ret_3y})
        
        # Plot
        if taiwan_etfs:
            _plot_2column_chart(taiwan_etfs, etf_type_prefix, '_TW', output_folder, 'Taiwan ETF')
        if us_etfs:
            _plot_2column_chart(us_etfs, etf_type_prefix, '_US', output_folder, 'US ETF')
        
        # print("✅ Chart generated successfully")
        
    except Exception as e:
        print(f"❌ Chart generation failed: {e}")

def _plot_2column_chart(etfs, etf_type_prefix, suffix, output_folder, title):
    """Plot 2-column chart"""
    import matplotlib.pyplot as plt
    import numpy as np
    
    plt.switch_backend('Agg')
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    
    try:
        fig, ax = plt.subplots(figsize=(14, 8))
        
        names = [f"{e['ticker']}\n{e['name']}" for e in etfs]
        x = np.arange(len(names))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, [e['ret_1y'] for e in etfs], width, 
                       label='1-Year', color='#3498db', alpha=0.85, edgecolor='black', linewidth=1)
        bars2 = ax.bar(x + width/2, [e['ret_3y'] for e in etfs], width, 
                       label='3-Year', color='#f1c40f', alpha=0.85, edgecolor='black', linewidth=1)
        
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                if height != 0:
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        ax.set_xlabel('ETF名稱', fontsize=FONT_SIZE_CONFIG['label_large'], fontweight='bold')
        ax.set_ylabel('報酬率（績效） (%)', fontsize=FONT_SIZE_CONFIG['label_large'], fontweight='bold')
        
        # 生成中文標題與時間戳
        chinese_title = f'{title} 年化報酬率（或績效）\n（藍色：1年 | 黃色：3年）'
        title_with_timestamp = generate_chart_title_with_timestamp(chinese_title)
        ax.set_title(title_with_timestamp,
                    fontsize=FONT_SIZE_CONFIG['title_large'], fontweight='bold', pad=20)
        ax.set_xticks(x)
        ax.set_xticklabels(names, fontsize=FONT_SIZE_CONFIG['tick_small'], rotation=45, ha='right')
        ax.axhline(y=0, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
        ax.grid(True, alpha=0.3, axis='y')
        ax.legend(fontsize=FONT_SIZE_CONFIG['label_medium'], loc='upper right')
        plt.tight_layout()
        
        os.makedirs(output_folder, exist_ok=True)
        output_path = os.path.join(output_folder, f'{etf_type_prefix.lower()}_performance_comparison{suffix}.png')
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"  ✅ {output_path}")
        
    except Exception as e:
        print(f"  ❌ Failed: {e}")
    finally:
        plt.close()


def plot_price_trend(etf_list, config, common_start_date, latest_date, etf_type_prefix="", output_folder=".", 
                     etf_data_dict=None, benchmark_data=None, voo_data=None):
    """繪製淨值成長折線圖（總圖+分類子圖，以基準指數正規化）
    ⚡ 優化版：全局快取基準數據，避免重複下載
    """
    plt = setup_matplotlib_backend()
    setup_chinese_font()
    
    # ⚡ 優化版：使用全局基準數據快取避免重複下載
    
    # 從 etf_list 提取信息（支持對象和數組格式）
    etf_info = {}
    etf_types = {}
    
    for item in etf_list:
        if isinstance(item, dict):
            # 對象格式：{"ticker": "...", "name": "...", "type": "..."}
            ticker = item.get('ticker', '').strip()
            name = item.get('name', '').strip()
            etf_type = item.get('type', 'tw_active').strip()
        else:
            # 數組格式：[ticker, name] 或 [ticker, name, type]
            ticker = item[0].strip()
            name = item[1].strip()
            etf_type = item[2].strip() if len(item) > 2 else 'tw_active'
        
        if ticker:
            etf_info[ticker] = name
            etf_types[ticker] = etf_type
    
    # 根據 JSON 中的分類信息分組 ETF
    us_etfs = {}
    tw_dividend_etfs = {}
    tw_stock_etfs = {}
    
    for ticker, name in etf_info.items():
        etf_type = etf_types.get(ticker, 'tw_active')
        
        if etf_type == 'us':
            us_etfs[ticker] = name
        elif etf_type == 'dividend':
            tw_dividend_etfs[ticker] = name
        else:
            tw_stock_etfs[ticker] = name
    
    # 1. 總覽圖（使用3年期間）
    def plot_overview():
        plt.figure(figsize=(16, 10))
        
        colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', 
                  '#FF9F40', '#C9CBCF', '#7BC225', '#FF5733', '#C70039', '#8B4513']
        
        # 先繪製基準指數（較粗的線條）
        # 使用傳入的基準數據，避免重複下載
        benchmark_0050_data = None
        try:
            # 📊 統一邏輯：0050也使用絕對正規化（起始點=100）
            if benchmark_data is not None:
                print("🔄 使用已下載的台灣50基準數據...")
                tw_prices = benchmark_data
                if isinstance(tw_prices, pd.DataFrame):
                    tw_prices = tw_prices['Close']
                    if isinstance(tw_prices, pd.DataFrame):
                        tw_prices = tw_prices.iloc[:, 0]
                
                # 0050使用絕對正規化：起始點 = 100
                normalized_0050 = (tw_prices / tw_prices.iloc[0]) * 100
                plt.plot(normalized_0050.index, normalized_0050, 
                        label='台灣50 (0050) 基準指數', linewidth=4, color='#FF0000', 
                        linestyle='-', alpha=0.9, zorder=10)
                benchmark_0050_data = tw_prices  # 保存原始數據
        except Exception as e:
            print(f"台灣50下載失敗: {e}")
        
        try:
            # 美股基準 - VOO ETF (使用全局快取)
            voo_prices = get_benchmark_data('VOO', common_start_date, latest_date, 'VOO S&P500 ETF')
            if voo_prices is not None:
                voo_normalized = (voo_prices / voo_prices.iloc[0]) * 100
                plt.plot(voo_normalized.index, voo_normalized, 
                        label='VOO S&P500 ETF', linewidth=3, color='#0000FF', 
                        linestyle='-.', alpha=0.8)
        except Exception as e:
            print(f"VOO ETF下載失敗: {e}")
        
        # 繪製各ETF（相對於0050的表現）- 使用已下載的數據
        for i, (ticker, name) in enumerate(etf_info.items()):
            try:
                # 🔄 使用傳入的ETF數據，避免重複下載
                if etf_data_dict and ticker in etf_data_dict:
                    df = etf_data_dict[ticker]
                    print(f"🔄 使用已下載數據: {ticker}")
                else:
                    # 備用：如果沒有傳入數據才下載
                    df = download_price_data(ticker.strip(), start_date=common_start_date, end_date=latest_date)
                    print(f"⚠️ 備用下載: {ticker}")
                
                if not df.empty:
                    prices = df['Close']
                    if isinstance(prices, pd.DataFrame):
                        prices = prices.iloc[:, 0]
                    
                    # 📊 統一使用絕對正規化：各ETF自己的起始點 = 100
                    normalized_prices = (prices / prices.iloc[0]) * 100
                    
                    color = colors[i % len(colors)]
                    line_style = '-'
                    alpha = 0.7
                    
                    # 使用簡化名稱
                    short_name = name.strip()
                    display_name = f"{ticker.replace('.TW', '')} {short_name}"
                    
                    plt.plot(normalized_prices.index, normalized_prices, 
                            label=display_name, linewidth=2, color=color, 
                            linestyle=line_style, alpha=alpha)
            except Exception as e:
                print(f"{ticker} 折線圖繪製失敗: {e}")
        
        # 設定標題和標籤（統一為絕對正規化）
        try:
            title = generate_chart_title_with_timestamp('ETF 淨值成長總覽\n各ETF起始點=100 | 基準指數=100 (水平線)')
            plt.title(title + " (2026-01-10 01:30生成)", fontsize=16, fontweight='bold')
            plt.xlabel('日期', fontsize=12)
            plt.ylabel('淨值成長 (起始點=100)', fontsize=12)
        except:
            plt.title(generate_chart_title_with_timestamp('ETF vs Benchmark Overview (Base=100)\nRed: Taiwan Index | Blue: VOO'), fontsize=16, fontweight='bold')
            plt.xlabel('Date', fontsize=12)
            plt.ylabel('Relative NAV (Start=100)', fontsize=12)
            
        plt.grid(True, alpha=0.3)
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', 
                   fontsize=12, frameon=True, fancybox=True, shadow=True,
                   title='圖例', title_fontsize=12)
        plt.axhline(y=100, color='gray', linestyle='-', linewidth=0.5, alpha=0.5)
        plt.tight_layout()
        
        # 儲存總覽圖到輸出資料夾
        try:
            output_path = os.path.join(output_folder, f'{etf_type_prefix}trend_overview.png')
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"✅ 總覽趨勢圖已儲存為: {output_path}")
        except Exception as e:
            try:
                output_path = os.path.join(output_folder, f'{etf_type_prefix}trend_overview.png')
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                print(f"✅ 總覽趨勢圖已儲存為: {output_path}")
            except:
                print(f"❌ 總覽趨勢圖儲存失敗: {e}")
        
        plt.close()
    
    # 2. 子圖函數：以基準指數正規化
    def plot_category_trend(etf_group, benchmark_ticker, benchmark_name, category_name, filename, benchmark_color, comparison_start_date, etf_type_prefix="", use_fixed_start=False, fixed_start_date=None):
        """繪製分類趨勢圖，以基準指數為標準正規化
        
        Args:
            use_fixed_start: 是否使用固定的起始日期（僅針對主動式ETF）
            fixed_start_date: 固定起始日期（如 '2025-07-22'）
        """
        
        if not etf_group:
            print(f"⚠️  {category_name}無ETF資料，跳過")
            return
        
        # 找出該組ETF的最晚上市日期 - 使用已下載的數據避免重複請求
        latest_etf_start = None
        etf_start_dates = {}
        
        print(f"\n🔍 檢查{category_name}ETF上市日期（使用已下載數據）...")
        for ticker in etf_group.keys():
            try:
                # ⚡ 優化：優先使用傳入的ETF數據推算上市日期
                if etf_data_dict and ticker in etf_data_dict:
                    df = etf_data_dict[ticker]
                    if not df.empty:
                        first_date = df.index.min()
                        etf_start_dates[ticker] = first_date
                        print(f"  {ticker}: 上市於 {first_date.strftime('%Y-%m-%d')} (已下載數據)")
                        
                        if latest_etf_start is None or first_date > latest_etf_start:
                            latest_etf_start = first_date
                        continue
                
                # ⚡ 次選：使用已有價格數據推算上市日期，避免重複下載
                cache_file = None
                # 修正快取路徑為當前日期
                from datetime import datetime
                today_str = datetime.now().strftime('%Y-%m-%d')
                potential_files = [
                    f"price_cache/active_etf/{ticker}_2025-07-22_to_{today_str}.csv",
                    f"price_cache/high_dividend_etf/{ticker}_*_to_{today_str}.csv", 
                    f"price_cache/industry_etf/{ticker}_*_to_{today_str}.csv",
                ]
                
                for file_pattern in potential_files:
                    import glob
                    matching_files = glob.glob(file_pattern.replace('*', '*'))
                    if matching_files:
                        cache_file = matching_files[0]
                        break
                
                if cache_file:
                    # 從快取讀取，避免網路請求
                    df = pd.read_csv(cache_file, index_col='Date', parse_dates=True)
                    if not df.empty:
                        first_date = df.index.min()
                        etf_start_dates[ticker] = first_date
                        print(f"  {ticker}: 上市於 {first_date.strftime('%Y-%m-%d')} (快取)")
                        
                        if latest_etf_start is None or first_date > latest_etf_start:
                            latest_etf_start = first_date
                    continue
                
                # 如果快取不存在，才進行網路下載（最後手段）
                search_start = '2020-01-01'
                df = download_price_data(ticker, start_date=search_start, end_date=latest_date)
                if not df.empty:
                    df.dropna(inplace=True)
                    if len(df) > 0:
                        etf_start = df.index[0]
                        etf_start_dates[ticker] = etf_start
                        print(f"  {ticker}: 上市於 {etf_start.strftime('%Y-%m-%d')}")
                        
                        if latest_etf_start is None or etf_start > latest_etf_start:
                            latest_etf_start = etf_start
            except Exception as e:
                print(f"  {ticker} 日期檢查失敗: {e}")
        
        if latest_etf_start is None:
            print(f"❌ {category_name}無法確定比較起始日期")
            return
        
        # comparison_start = latest_etf_start.strftime('%Y-%m-%d')
        # 使用傳入的 comparison_start_date 而不是全域的 common_start_date
        print(f"📅 {category_name}統一比較期間: {comparison_start_date} 至 {latest_date}")
        
        plt.figure(figsize=(14, 8))
        
        # 下載並繪製基準指數（作為正規化基準）
        benchmark_data = None
        try:
            print(f"📊 下載{benchmark_name}基準資料...")
            
            # 使用統一的基準數據下載機制
            benchmark_df = download_price_data(benchmark_ticker, start_date=comparison_start_date, end_date=latest_date)
                
            if not benchmark_df.empty:
                benchmark_prices = benchmark_df['Close']
                if isinstance(benchmark_prices, pd.DataFrame):
                    benchmark_prices = benchmark_prices.iloc[:, 0]
                
                benchmark_data = benchmark_prices  # 保存原始價格用於正規化
                
                # 基準就是100（畫一條水平線）
                plt.axhline(y=100, color=benchmark_color, linestyle='-', linewidth=4, 
                           label=f'{benchmark_name} (基準=100)', alpha=0.9, zorder=10)
        except Exception as e:
            print(f"{benchmark_name}基準下載失敗: {e}")
        
        # 繪製該組ETF，使用絕對正規化（各自從100開始）- 避免重複下載
        colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#C70039', '#7BC225']
        
        for i, (ticker, name) in enumerate(etf_group.items()):
            try:
                # ⚡ 優化：優先使用快取，避免重複網路請求
                df = None
                cache_file = None
                potential_files = [
                    f"price_cache/active_etf/{ticker}_{comparison_start_date}_to_{latest_date}.csv",
                    f"price_cache/high_dividend_etf/{ticker}_{comparison_start_date}_to_{latest_date}.csv", 
                    f"price_cache/industry_etf/{ticker}_{comparison_start_date}_to_{latest_date}.csv",
                ]
                
                for file_path in potential_files:
                    if os.path.exists(file_path):
                        try:
                            df = pd.read_csv(file_path, index_col='Date', parse_dates=True)
                            print(f"  📦 使用快取: {ticker} (避免重複下載)")
                            break
                        except:
                            continue
                
                # 如果快取不存在或失敗，才進行網路下載
                if df is None or df.empty:
                    df = download_price_data(ticker, start_date=comparison_start_date, end_date=latest_date)
                
                if not df.empty:
                    etf_prices = df['Close']
                    if isinstance(etf_prices, pd.DataFrame):
                        etf_prices = etf_prices.iloc[:, 0]
                    
                    # 對齐日期：找出 ETF 和基準的共同日期
                    if benchmark_data is not None:
                        common_dates = etf_prices.index.intersection(benchmark_data.index)
                        if len(common_dates) > 0:
                            etf_aligned = etf_prices.loc[common_dates]
                            benchmark_aligned = benchmark_data.loc[common_dates]
                            
                            # 相對表現 = (ETF漲幅 / 基準漲幅) × 100
                            # 使用 2025-07-22 或 ETF 上市日期中較晚者作為起始點
                            comparison_date = pd.to_datetime(comparison_start_date)
                            etf_start_date = etf_prices.index[0]
                            use_start_date = max(comparison_date, etf_start_date)
                            
                            # 找出起始點的價格
                            if use_start_date in etf_aligned.index and use_start_date in benchmark_aligned.index:
                                etf_start_price = etf_aligned.loc[use_start_date]
                                benchmark_start_price = benchmark_aligned.loc[use_start_date]
                                
                                # 對齐到起始日期之後的資料
                                etf_aligned = etf_aligned.loc[etf_aligned.index >= use_start_date]
                                benchmark_aligned = benchmark_aligned.loc[benchmark_aligned.index >= use_start_date]
                                
                                # 相對報酬
                                etf_return = etf_aligned / etf_start_price
                                benchmark_return = benchmark_aligned / benchmark_start_price
                                etf_normalized = (etf_return / benchmark_return) * 100
                                plot_index = etf_aligned.index
                            else:
                                # 找不到精確起始點，使用共同日期的第一個
                                etf_start_price = etf_aligned.iloc[0]
                                benchmark_start_price = benchmark_aligned.iloc[0]
                                etf_return = etf_aligned / etf_start_price
                                benchmark_return = benchmark_aligned / benchmark_start_price
                                etf_normalized = (etf_return / benchmark_return) * 100
                                plot_index = etf_aligned.index
                        else:
                            # 如果沒有共同日期，使用 ETF 自己的範圍正規化
                            etf_normalized = (etf_prices / etf_prices.iloc[0]) * 100
                            plot_index = etf_prices.index
                    else:
                        # 如果沒有基準資料，使用 ETF 自己的範圍正規化
                        etf_normalized = (etf_prices / etf_prices.iloc[0]) * 100
                        plot_index = etf_prices.index
                    
                    color = colors[i % len(colors)]
                    
                    # 使用簡化的名稱
                    short_name = name.strip()
                    display_name = f"{ticker.replace('.TW', '')} {short_name}"
                    
                    # 主動型ETF用實線，被動型用虛線
                    line_style = '-' if '主動' in name else '--'
                    
                    plt.plot(plot_index, etf_normalized, 
                            label=display_name, linewidth=2.5, color=color, 
                            linestyle=line_style, alpha=0.8)
            except Exception as e:
                print(f"  {ticker} 繪製失敗: {e}")
        
        # 設定標題和標籤
        try:
            if benchmark_data is not None:
                title = f'{category_name} vs {benchmark_name}\n相對表現 (基準指數=100基準線)'
                ylabel = f'相對表現 (vs {benchmark_name})'
            else:
                title = f'{category_name} 表現比較\n(各自起始點=100)'
                ylabel = '相對淨值 (起始=100)'
            
            plt.title(generate_chart_title_with_timestamp(title), fontsize=14, fontweight='bold')
            plt.xlabel('日期', fontsize=12)
            plt.ylabel(ylabel, fontsize=12)
        except:
            plt.title(f'{category_name} Performance', fontsize=14, fontweight='bold')
            plt.xlabel('Date', fontsize=12)
            plt.ylabel('Relative Performance', fontsize=12)
        
        # 添加重要參考線
        plt.axhline(y=100, color='gray', linestyle='-', linewidth=1, alpha=0.7, label='基準線')
        plt.axhline(y=110, color='green', linestyle=':', linewidth=1, alpha=0.5, label='+10%')
        plt.axhline(y=90, color='red', linestyle=':', linewidth=1, alpha=0.5, label='-10%')
        
        plt.grid(True, alpha=0.3)
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', 
                   fontsize=14, frameon=True, fancybox=True, shadow=True,
                   title=f'{category_name}\n實線：主動型\n虛線：被動型', title_fontsize=12)
        plt.tight_layout()
        
        # 儲存子圖到輸出資料夾
        try:
            output_path = os.path.join(output_folder, f'{etf_type_prefix}{filename}')
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"✅ {category_name}趨勢圖已儲存為: {output_path}")
        except Exception as e:
            try:
                output_path = os.path.join(output_folder, f'{etf_type_prefix}{filename}')
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                print(f"✅ {category_name}趨勢圖已儲存為: {output_path}")
            except:
                print(f"❌ {category_name}趨勢圖儲存失敗: {e}")
        
        plt.close()
    
    # 執行繪製
    # 從 etf_type_prefix 推斷配置類型
    if etf_type_prefix == 'Active_':
        config_type = 'active_etf'
    elif etf_type_prefix == 'HighDividend_':
        config_type = 'high_dividend_etf'
    elif etf_type_prefix == 'Industry_':
        config_type = 'industry_etf'
    else:
        config_type = 'default'
    
    # 判斷是否為主動式 ETF（使用固定起始日期）
    use_fixed_start_for_trends = (config_type == 'active_etf')
    # 使用傳入的日期參數而不是未定義的變數
    fixed_start_date_for_trends = common_start_date if use_fixed_start_for_trends else None
    
    # 總覽圖
    plot_overview()
    
    # 美股相關ETF vs VOO ETF
    plot_category_trend(
        us_etfs, 
        'VOO', 
        'VOO ETF', 
        '美股相關ETF', 
        'trend_us_etfs.png',
        '#0066CC',
        common_start_date,
        etf_type_prefix,
        use_fixed_start=use_fixed_start_for_trends,
        fixed_start_date=fixed_start_date_for_trends
    )
    
    # 台股高股息ETF vs 元大高股息(0056)
    plot_category_trend(
        tw_dividend_etfs, 
        '0056.TW', 
        '元大高股息', 
        '台股高股息ETF', 
        'trend_tw_dividend.png',
        '#FF6600',
        common_start_date,
        etf_type_prefix,
        use_fixed_start=use_fixed_start_for_trends,
        fixed_start_date=fixed_start_date_for_trends
    )
    
    # 台股股票型ETF vs 台灣50(0050)
    plot_category_trend(
        tw_stock_etfs, 
        '0050.TW', 
        '台灣50', 
        '台股股票型ETF', 
        'trend_tw_stock.png',
        '#CC0000',
        common_start_date,
        etf_type_prefix,
        use_fixed_start=use_fixed_start_for_trends,
        fixed_start_date=fixed_start_date_for_trends
    )
    
    print(f"\n📊 趨勢圖繪製完成！")
    print(f"✅ 總覽圖: {etf_type_prefix}trend_overview.png")
    print(f"✅ 美股相關: {etf_type_prefix}trend_us_etfs.png")
    print(f"✅ 台股高股息: {etf_type_prefix}trend_tw_dividend.png") 
    print(f"✅ 台股股票型: {etf_type_prefix}trend_tw_stock.png")
    
    # 輸出分析摘要
    print(f"\n📊 趨勢圖分析方式:")
    print(f"  📈 總覽圖: 3年期間，各自起始點=100")
    print(f"  📊 子圖: 以最晚上市ETF為起始，基準指數=100")
    print(f"  🎯 相對表現: >100表示跑贏基準，<100表示跑輸基準")
    print(f"  📏 實線/虛線: 區分主動型/被動型ETF")


def plot_multi_metrics_comparison(df_results, etf_type_prefix="", output_folder=".", annualize=True):
    """繪製多指標柱狀圖：績效/年化報酬率、Alpha、Beta、夏普比率、MDD、標準差、費用率、追蹤誤差"""
    plt = setup_matplotlib_backend()
    setup_chinese_font()

    # print("\n📊 繪製多指標比較柱狀圖...")
    
    # 決定績效列的名稱
    if annualize:
        return_col = '1年年化報酬率 (%)'
        return_label = '1年年化報酬率 (%)'
    else:
        return_col = '績效 (%)'
        return_label = '績效 (%)'
    
    # 準備數據 - 根據 annualize 參數動態調整
    metrics = {
        return_label: {'col': return_col, 'color': '#FF6384', 'format': '.2f'},
        'Alpha': {'col': 'Alpha', 'color': '#36A2EB', 'format': '.2f'},
        'Beta': {'col': 'Beta', 'color': '#4BC0C0', 'format': '.2f'},
        '夏普比率': {'col': '夏普比率', 'color': '#FF9F40', 'format': '.2f'},
        '最大回撤 (%)': {'col': '最大回撤 (%)', 'color': '#FF5733', 'format': '.2f'},
        '標準差 (%)': {'col': '年化波動率 (%)', 'color': '#9966FF', 'format': '.2f'},
        '費用率 (%)': {'col': '管理費 (%)', 'color': '#FFCE56', 'format': '.2f'},
        '追蹤誤差 (%)': {'col': '追蹤誤差 (%)', 'color': '#C9CBCF', 'format': '.2f'},
    }
    
    # 創建 2x4 子圖佈局
    fig, axes = plt.subplots(2, 4, figsize=(24, 12))
    axes = axes.flatten()
    
    # 決定要排序的列名
    sort_col = '1年年化報酬率 (%)' if annualize else '績效 (%)'
    
    # 排序ETF：按報酬率降序
    df_sorted = df_results.sort_values(sort_col, ascending=False)
    
    tickers = df_sorted['證券代碼'].str.strip().values
    names = df_sorted['名稱'].str.strip().values
    
    # 為每個指標繪製柱狀圖
    for idx, (metric_name, metric_info) in enumerate(metrics.items()):
        ax = axes[idx]
        col = metric_info['col']
        color = metric_info['color']
        fmt = metric_info['format']
        
        # 獲取數據
        try:
            values = pd.to_numeric(df_sorted[col], errors='coerce').fillna(0)
        except KeyError:
            print(f"  ⚠️  警告: 未找到欄位 '{col}'，跳過此指標")
            ax.text(0.5, 0.5, f'缺少數據: {col}', ha='center', va='center', 
                   transform=ax.transAxes, fontsize=12)
            continue
        
        # 繪製柱狀圖
        x_pos = np.arange(len(names))
        bars = ax.bar(x_pos, values, color=color, alpha=0.7, edgecolor='black', linewidth=1)
        
        # 添加數值標籤
        for bar, val in zip(bars, values):
            if pd.notna(val) and val != 0:
                height = bar.get_height()
                label_y = height + (max(values) * 0.02) if height >= 0 else height - (max(values) * 0.05)
                ax.text(bar.get_x() + bar.get_width()/2., label_y,
                       f'{val:{fmt}}', ha='center', va='bottom' if height >= 0 else 'top',
                       fontsize=12, fontweight='bold')
        
        # 設置標題和標籤
        ax.set_title(metric_name, fontsize=FONT_SIZE_CONFIG['title_small']-4, fontweight='bold', pad=15)
        ax.set_ylabel('數值', fontsize=FONT_SIZE_CONFIG['label_medium'], fontweight='bold')
        ax.set_xticks(x_pos)
        
        # 簡化X軸標籤（只顯示代碼）
        ax.set_xticklabels([t.replace('.TW', '') for t in tickers], 
                           rotation=45, ha='right', fontsize=10)
        
        # 網格和零線
        ax.grid(True, alpha=0.3, axis='y')
        if values.min() < 0 < values.max():
            ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
        
        # 找出冠軍（最高值）
        if pd.notna(values).any():
            max_idx = values.idxmax()
            champion_name = df_sorted.iloc[values.values.tolist().index(values[max_idx])]['名稱'].strip()
            champion_ticker = df_sorted.iloc[values.values.tolist().index(values[max_idx])]['證券代碼'].strip()
            max_val = values[max_idx]
            print(f"  🏆 {metric_name}: {champion_ticker} ({champion_name}) - {max_val:{fmt}}")
    
    # 總標題（添加時間戳）
    from datetime import datetime
    current_time = datetime.now().strftime('%Y%m%d %H:%M')
    fig.suptitle(f'ETF 多指標性能比較表 {current_time}生成', fontsize=FONT_SIZE_CONFIG['title_large'], 
                fontweight='bold', y=0.995)
    
    # 添加說明
    fig.text(0.5, 0.01, '包含: 年化報酬率、Alpha、Beta、夏普比率、最大回撤、標準差、費用率、追蹤誤差',
             ha='center', fontsize=FONT_SIZE_CONFIG['figure_text'], style='italic')
    
    plt.tight_layout()
    plt.subplots_adjust(top=0.93, bottom=0.10, hspace=0.35, wspace=0.3)
    
    # 保存圖表
    try:
        output_path = os.path.join(output_folder, f'{etf_type_prefix}etf_multi_metrics_comparison.png')
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        # print(f"\n✅ 多指標圖表已儲存: {output_path}")
    except Exception as e:
        print(f"❌ 保存多指標圖表失敗: {e}")
    
    plt.close()


def plot_dual_column_performance(df_results, benchmark_data=None, etf_type_prefix=""):
    """繪製雙柱狀圖表：ETF 1年年化報酬率 vs 基準指數年化報酬率"""
    plt = setup_matplotlib_backend()
    setup_chinese_font()
    
    print("\n📊 繪製雙柱狀績效圖表（1年 vs 3年）...")
    
    try:
        fig, ax = plt.subplots(figsize=(16, 9))
        
        # 準備數據
        names = []
        ret_etf_list = []  # ETF 1年年化報酬率
        ret_bench_list = []  # 基準報酬率
        
        # 決定用哪個基準（台股或美股）
        benchmark_key_1y = '0050'  # 1年基準
        benchmark_key_3y = '0050'  # 3年基準
        if etf_type_prefix.startswith('HighDividend'):
            benchmark_key_1y = '0050'
            benchmark_key_3y = '0050'
        elif etf_type_prefix.startswith('US'):
            benchmark_key_1y = 'VOO'
            benchmark_key_3y = 'VOO'
        
        # 獲取基準報酬率
        bench_ret_1y = 0
        bench_ret_3y = 0
        bench_name = '基準'
        if benchmark_data and benchmark_key_1y in benchmark_data:
            bench_name, bench_ret_1y = benchmark_data[benchmark_key_1y]
        if benchmark_data and benchmark_key_3y in benchmark_data:
            _, bench_ret_3y = benchmark_data[benchmark_key_3y]
        
        # 準備 ETF 數據
        names = []
        ret_etf_1y_list = []  # ETF 1年年化報酬率
        ret_etf_3y_list = []  # ETF 3年年化報酬率
        ret_bench_1y_list = []  # 基準 1年
        ret_bench_3y_list = []  # 基準 3年
        
        for _, row in df_results.iterrows():
            ticker = row['證券代碼'].strip()
            name = row['名稱'].strip()
            
            # 1 年年化報酬率
            ret_1y = row.get('1年年化報酬率 (%)', 'N/A')
            ret_1y = float(ret_1y) if ret_1y != 'N/A' and ret_1y != 9999 else 0
            
            # 3 年年化報酬率
            ret_3y = row.get('3年年化報酬率 (%)', 'N/A')
            ret_3y = float(ret_3y) if ret_3y != 'N/A' and ret_3y != 9999 else 0
            
            names.append(f"{ticker}\n{name}")
            ret_etf_1y_list.append(ret_1y)
            ret_etf_3y_list.append(ret_3y)
            ret_bench_1y_list.append(bench_ret_1y)
            ret_bench_3y_list.append(bench_ret_3y)
        
        # 設定 X 軸位置
        x = np.arange(len(names))
        width = 0.35
        
        # 繪製 4 根柱子
        width = 0.2
        offset = width * 1.5
        
        bars1 = ax.bar(x - offset, ret_etf_1y_list, width, label='ETF 1年年化', 
                       color='#3498db', alpha=0.85, edgecolor='black', linewidth=1)
        bars2 = ax.bar(x - width/2, ret_etf_3y_list, width, label='ETF 3年年化', 
                       color='#f39c12', alpha=0.85, edgecolor='black', linewidth=1)
        bars3 = ax.bar(x + width/2, ret_bench_1y_list, width, label=f'{bench_name} 1年', 
                       color='#95a5a6', alpha=0.85, edgecolor='black', linewidth=1)
        bars4 = ax.bar(x + offset, ret_bench_3y_list, width, label=f'{bench_name} 3年', 
                       color='#52be80', alpha=0.85, edgecolor='black', linewidth=1)
        
        # 添加數值標籤
        for bar in bars1 + bars2 + bars3 + bars4:
            height = bar.get_height()
            if height != 0 and height != 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}%', ha='center', va='bottom', fontsize=8, fontweight='bold')
        
        # 設定標籤
        ax.set_xlabel('ETF', fontsize=FONT_SIZE_CONFIG['label_large'], fontweight='bold')
        ax.set_ylabel('年化報酬率 (% / 年)', fontsize=FONT_SIZE_CONFIG['label_large'], fontweight='bold')
        ax.set_title(f'ETF 績效對比：1年 & 3年 vs {bench_name}\n（藍色：ETF 1年 | 黃色：ETF 3年 | 灰色：基準 1年 | 綠色：基準 3年）',
                    fontsize=FONT_SIZE_CONFIG['title_large'], fontweight='bold', pad=20)
        ax.set_xticks(x)
        ax.set_xticklabels(names, fontsize=FONT_SIZE_CONFIG['tick_small'], rotation=45, ha='right')
        
        # 添加基準線
        ax.axhline(y=0, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
        ax.grid(True, alpha=0.3, axis='y')
        
        # 圖例
        ax.legend(fontsize=FONT_SIZE_CONFIG['label_medium'], loc='upper right', 
                 frameon=True, fancybox=True, shadow=True)
        plt.tight_layout()
        
        # 保存
        output_path = os.path.join(output_folder, f'{etf_type_prefix}etf_dual_column_performance.png')
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"  ✅ 雙柱狀圖表已儲存: {output_path}")
        
    except Exception as e:
        print(f"  ❌ 雙柱狀圖表生成失敗: {e}")
    
    plt.close()


def plot_performance_comparison(df_results, ret_1y_dict=None, ret_3y_dict=None, benchmark_data=None, etf_type_prefix="", annualize=True):
    """繪製績效比較柱狀圖 - 自動根據 ETF 類型生成 _TW 或 _US 版本"""
    plt = setup_matplotlib_backend()
    setup_chinese_font()

    print("\n📊 繪製績效比較柱狀圖...")
    
    # 分類 ETF
    taiwan_etfs = []
    us_etfs = []
    
    for _, row in df_results.iterrows():
        name = row['名稱'].strip()
        ticker = row['證券代碼'].strip()
        ret = float(row.get('1年年化報酬率 (%)', 'N/A')) if row.get('1年年化報酬率 (%)', 'N/A') != 'N/A' else 0
        
        # 分類邏輯：美股 vs 台股
        # 美股相關 ETF：00646、00662、00757、00983A（ARK創新）、00988A（統一全球創新）、00989A（摩根美國科技）
        if '美股' in name or 'US' in name or any(code in ticker for code in ['00646', '00662', '00757', '00983A', '00988A', '00989A']):
            us_etfs.append((name, ret, ticker))
            print(f"  ✅ 美股: {ticker:12} - {ret:7.2f}%")
        else:
            taiwan_etfs.append((name, ret, ticker))
            print(f"  🔵 台股: {ticker:12} - {ret:7.2f}%")
    
    # 先下載基準數據（Y軸調整需要用到）
    print("  📥 下載基準指數...")
    benchmark_data = {}
    
    # 決定基準指數的時間範圍和計算方式
    # 對於 active_etf，統一使用 common_start_date（從 2025-07-22 開始），計算實績
    # 對於其他類別，使用更長期的數據（1年），計算年化
    if config_type == 'active_etf':
        bench_start_date = common_start_date  # 統一使用 2025-07-22
        bench_annualize = False  # 計算實績，不年化
        print(f"  📊 基準指數時間範圍: {bench_start_date} 至 {latest_date}（與主動式 ETF 統一，計算實績）")
    else:
        from datetime import datetime as dt_now
        latest_dt = dt_now.strptime(latest_date, '%Y-%m-%d')
        benchmark_start_dt = latest_dt - timedelta(days=365)
        bench_start_date = benchmark_start_dt.strftime('%Y-%m-%d')
        bench_annualize = True  # 計算年化
        print(f"  📊 基準指數時間範圍: {bench_start_date} 至 {latest_date}（過去1年，計算年化）")
    
    try:
        # 台股基準
        benchmark_0050 = download_price_data('0050.TW', start_date=bench_start_date, end_date=latest_date)
        benchmark_006208 = download_price_data('006208.TW', start_date=bench_start_date, end_date=latest_date)
        
        if isinstance(benchmark_0050, pd.DataFrame) and not benchmark_0050.empty:
            years_0050 = len(benchmark_0050['Close']) / 252
            total_ret_0050 = ((benchmark_0050['Close'].iloc[-1] / benchmark_0050['Close'].iloc[0]) - 1) * 100
            
            if bench_annualize and years_0050 >= 1.0:
                ret_0050 = float(((1 + total_ret_0050/100) ** (1 / years_0050) - 1) * 100) if years_0050 > 0 else total_ret_0050
                benchmark_data['0050'] = ('0050 台灣50', ret_0050)
            else:
                ret_0050 = float(total_ret_0050)
                benchmark_data['0050'] = ('0050 台灣50', ret_0050)
        
        if isinstance(benchmark_006208, pd.DataFrame) and not benchmark_006208.empty:
            years_006208 = len(benchmark_006208['Close']) / 252
            total_ret_006208 = ((benchmark_006208['Close'].iloc[-1] / benchmark_006208['Close'].iloc[0]) - 1) * 100
            
            if bench_annualize and years_006208 >= 1.0:
                ret_006208 = float(((1 + total_ret_006208/100) ** (1 / years_006208) - 1) * 100) if years_006208 > 0 else total_ret_006208
                benchmark_data['006208'] = ('006208 富邦台50', ret_006208)
            else:
                ret_006208 = float(total_ret_006208)
                benchmark_data['006208'] = ('006208 富邦台50', ret_006208)
        
        # 美股基準（使用全局快取，跨ETF類型復用）
        if us_etfs:
            # 使用VOO作為美股基準
            voo_prices = get_benchmark_data('VOO', bench_start_date, latest_date, 'VOO S&P500 ETF')
            if voo_prices is not None:
                years_voo = len(voo_prices) / 252
                total_ret_voo = ((voo_prices.iloc[-1] / voo_prices.iloc[0]) - 1) * 100
                
                if bench_annualize and years_voo >= 1.0:
                    ret_voo = float(((1 + total_ret_voo/100) ** (1 / years_voo) - 1) * 100) if years_voo > 0 else total_ret_voo
                else:
                    ret_voo = float(total_ret_voo)
                benchmark_data['VOO'] = ('VOO S&P500', ret_voo)
            else:
                print("⚠️ VOO基準數據無法取得")
    except Exception as e:
        print(f"  ⚠️  基準下載失敗: {e}")
    
    # 調試：打印基準指數數據
    bench_label = "實績" if not bench_annualize else "年化報酬率"
    print(f"\n📊 基準指數{bench_label}:")
    for key, (name, ret) in benchmark_data.items():
        print(f"  {name}: {ret:.2f}%")
    
    # 計算Y軸範圍（包含基準數據）
    all_returns_for_scale = [item[1] for item in taiwan_etfs + us_etfs]
    # 也加上基準數據
    for key in ['0050', '006208', 'VOO', 'SP500']:
        if key in benchmark_data:
            all_returns_for_scale.append(benchmark_data[key][1])
    
    if all_returns_for_scale:
        # 自動調整 Y 軸，留出足夠空間顯示標籤
        data_min = min(all_returns_for_scale)
        data_max = max(all_returns_for_scale)
        data_range = data_max - data_min if data_max != data_min else 1
        
        # 留出 15% 上下空間
        y_min = data_min - data_range * 0.15
        y_max = data_max + data_range * 0.15
    else:
        y_min, y_max = -10, 50
    
    # 繪製台股 ETF 圖表（_TW 版本）
    if taiwan_etfs:
        # print(f"\n  📊 生成台股 ETF 柱狀圖 (_TW)...")
        fig, ax = plt.subplots(figsize=(16, 9))
        
        names = [item[0] for item in taiwan_etfs]
        returns = [item[1] for item in taiwan_etfs]
        tickers = [item[2] for item in taiwan_etfs]
        
        # 根據名稱判斷顏色：主動型 vs 被動型 vs 高股息
        colors = []
        for name in names:
            if '主動' in name:
                colors.append('#FF6384')  # 紅色 - 主動型
            elif any(keyword in name for keyword in ['高股息', '高息', '永續', '股利']):
                colors.append('#FF9F40')  # 橙色 - 高股息
            else:
                colors.append('#36A2EB')  # 藍色 - 一般被動型
        
        # 添加基準數據
        benchmark_names = []
        benchmark_returns = []
        benchmark_colors = []
        for key in ['0050', '006208']:
            if key in benchmark_data:
                name, ret = benchmark_data[key]
                benchmark_names.append(name)
                benchmark_returns.append(ret)
                benchmark_colors.append('#D3D3D3')  # 灰色 - 基準
        
        # 合併數據
        all_names = names + benchmark_names
        all_returns = returns + benchmark_returns
        all_colors = colors + benchmark_colors
        
        x_pos = np.arange(len(all_names))
        bars = ax.bar(x_pos, all_returns, color=all_colors, alpha=0.7, edgecolor='black', linewidth=1.5)
        
        # 添加數值標籤
        for bar, ret in zip(bars, all_returns):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                   f'{ret:.1f}%', ha='center', va='bottom',
                   fontsize=FONT_SIZE_CONFIG['label_medium'], fontweight='bold')
        
        title_tw = generate_chart_title_with_timestamp('台股 ETF 三年年化報酬率比較 (含基準指數)')
        ax.set_title(title_tw, fontsize=FONT_SIZE_CONFIG['title_large'], fontweight='bold')
        ax.set_ylabel('3年年化報酬率 (%)', fontsize=FONT_SIZE_CONFIG['label_large'], fontweight='bold')
        ax.set_xticks(x_pos)
        
        # 改進 X 軸標籤：顯示完整的 ETF 名稱 + 代碼，垂直排列
        labels = []
        for i, name in enumerate(all_names):
            if i < len(names):
                # ETF：顯示完整名稱
                ticker = tickers[i].replace('.TW', '')
                etf_name = names[i]
                labels.append(f"{ticker} {etf_name}")
            else:
                # 基準：顯示完整名稱
                labels.append(name)
        
        # 垂直排列標籤
        ax.set_xticklabels(labels, rotation=90, fontsize=FONT_SIZE_CONFIG['tick_small'], ha='right')
        
        # 增加底部空間以容納垂直標籤
        plt.subplots_adjust(bottom=0.35)
        
        ax.set_ylim(y_min, y_max)
        ax.grid(True, alpha=0.3, axis='y')
        ax.axhline(y=0, color='black', linestyle='-', linewidth=1)
        
        # 設置中文標題和時間戳
        title_with_timestamp = generate_chart_title_with_timestamp("台股ETF年化報酬率比較")
        ax.set_title(title_with_timestamp, fontsize=FONT_SIZE_CONFIG['title_large'], fontweight='bold')
        
        plt.tight_layout()
        
        # 保存
        try:
            output_path = os.path.join(output_folder, f'{etf_type_prefix}etf_performance_comparison_TW.png')
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"  ✅ 台股 ETF 柱狀圖已儲存: {etf_type_prefix}etf_performance_comparison_TW.png ({current_time})")
        except Exception as e:
            print(f"  ❌ 保存失敗: {e}")
        
        plt.close()
    
    # 繪製美股 ETF 圖表（_US 版本）
    if us_etfs:
        print(f"\n  📊 生成美股 ETF 柱狀圖 (_US)...")
        fig, ax = plt.subplots(figsize=(14, 9))
        
        names = [item[0] for item in us_etfs]
        returns = [item[1] for item in us_etfs]
        tickers = [item[2] for item in us_etfs]
        
        # 美股 ETF 顏色
        color_map = {
            '00983A': '#FF9F40',  # ARK創新 - 橙色
            '00646': '#4BC0C0',   # S&P500 - 青色
            '00662': '#9966FF',   # NASDAQ - 紫色
            '00757': '#FF5733',   # FANG+ - 紅橙色
        }
        
        colors = []
        for ticker in tickers:
            found = False
            for code, color in color_map.items():
                if code in ticker:
                    colors.append(color)
                    found = True
                    break
            if not found:
                colors.append('#8B7355')
        
        # 添加基準數據
        benchmark_names = []
        benchmark_returns = []
        benchmark_colors = []
        for key in ['VOO', 'SP500']:
            if key in benchmark_data:
                name, ret = benchmark_data[key]
                benchmark_names.append(name)
                benchmark_returns.append(ret)
                benchmark_colors.append('#D3D3D3')
        
        # 合併數據
        all_names = names + benchmark_names
        all_returns = returns + benchmark_returns
        all_colors = colors + benchmark_colors
        
        x_pos = np.arange(len(all_names))
        bars = ax.bar(x_pos, all_returns, color=all_colors, alpha=0.7, edgecolor='black', linewidth=1.5)
        
        # 添加數值標籤
        for bar, ret in zip(bars, all_returns):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                   f'{ret:.1f}%', ha='center', va='bottom',
                   fontsize=FONT_SIZE_CONFIG['label_medium'], fontweight='bold')
        
        ax.set_title(generate_chart_title_with_timestamp('美股 ETF 年化報酬率比較 (含基準)'), fontsize=FONT_SIZE_CONFIG['title_large'], fontweight='bold')
        ax.set_ylabel('3年年化報酬率 (%)', fontsize=FONT_SIZE_CONFIG['label_large'], fontweight='bold')
        ax.set_xticks(x_pos)
        
        # 改進 X 軸標籤：顯示完整的 ETF 名稱 + 代碼，垂直排列
        labels = []
        for i, name in enumerate(all_names):
            if i < len(names):
                # ETF：顯示完整名稱
                ticker = tickers[i].replace('.TW', '')
                etf_name = names[i]
                labels.append(f"{ticker} {etf_name}")
            else:
                # 基準：顯示完整名稱
                labels.append(name)
        
        # 垂直排列標籤
        ax.set_xticklabels(labels, rotation=90, fontsize=FONT_SIZE_CONFIG['tick_small'], ha='right')
        
        # 增加底部空間以容納垂直標籤
        plt.subplots_adjust(bottom=0.35)
        
        ax.set_ylim(y_min, y_max)
        ax.grid(True, alpha=0.3, axis='y')
        ax.axhline(y=0, color='black', linestyle='-', linewidth=1)
        
        # 在保存前添加時間戳到標題
        from datetime import datetime
        current_time = datetime.now().strftime('%Y%m%d %H:%M')
        timestamp_title = f'美股 ETF 年化報酬率比較 (含基準) {current_time}生成'
        ax.set_title(timestamp_title, fontsize=FONT_SIZE_CONFIG['title_large'], fontweight='bold')
        
        plt.tight_layout()
        
        # 保存
        try:
            output_path = os.path.join(output_folder, f'{etf_type_prefix}etf_performance_comparison_US.png')
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"  ✅ 美股 ETF 柱狀圖已儲存: {etf_type_prefix}etf_performance_comparison_US.png ({current_time})")
        except Exception as e:
            print(f"  ❌ 保存失敗: {e}")
        
        plt.close()

