#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自動抓取台灣 ETF 費用率並更新 JSON 配置
數據來源：
1. Yahoo Finance API
2. 本地緩存數據庫
3. 手動輸入
"""

import json
import os
from datetime import datetime
import yfinance as yf

# 已知的費用率數據（台灣 ETF）
KNOWN_EXPENSE_RATIOS = {
    # 主動型 ETF
    '00980A.TW': 0.785,      # 主動野村台灣優選
    '00981A.TW': 1.32,       # 主動統一台股增長
    '00982A.TW': 0.835,      # 主動群益台灣強棒
    '00983A.TW': 1.0,        # 主動中信ARK創新
    '00985A.TW': 0.485,      # 主動野村台灣50
    '00980D.TW': 0.77,       # 主動聯博投等入息
    '00984A.TW': 0.74,       # 主動安聯台灣高息
    '00991A.TW': 0.9,        # 主動復華未來50
    '00992A.TW': 1.0,        # 主動群益台灣科技創新
    '00986A.TW': 0.95,       # 主動台新龍頭成長
    '00988A.TW': 1.05,       # 主動統一全球創新
    '00989A.TW': 1.1,        # 主動摩根美國科技
    
    # 被動型 ETF（台股）
    '0050.TW': 0.13,         # 台灣50
    '006208.TW': 0.185,      # 富邦台50
    '0056.TW': 0.6,          # 元大高股息
    '00878.TW': 0.42,        # 國泰永續高股息
    
    # 美股 ETF
    '00646.TW': 0.66,        # 元大S&P500
    '00662.TW': 0.51,        # 富邦NASDAQ
    '00757.TW': 1.15,        # 統一FANG+
    
    # 高股息 ETF
    '00929.TW': 0.6,         # 復華台灣科技優息
    '00934.TW': 0.7,         # 中信成長高股息
    '00936.TW': 0.75,        # 台新永續高息中小
    '00939.TW': 0.68,        # 統一台灣高息動能
    '00940.TW': 0.65,        # 元大台灣價值高息
    '00944.TW': 0.72,        # 野村趨勢動能高息
    '00946.TW': 0.7,         # 群益科技高息成長
    '00961.TW': 0.78,        # FT臺灣永續高息
    '00943.TW': 0.75,        # 兆豐電子高股息等權
    '00713.TW': 0.59,        # 元大台灣高息低波
    '00915.TW': 0.74,        # 凱基優選高股息30
    '00918.TW': 0.76,        # 大華優利高填息30
    '00919.TW': 0.59,        # 群益台灣精選高息
    '00932.TW': 0.68,        # 兆豐永續高息等權
    '00731.TW': 0.64,        # 復華富時高息低波
    '00900.TW': 0.58,        # 富邦特選高股息30
    '00927.TW': 0.8,         # 群益半導體收益
    '00907.TW': 0.66,        # 永豐優息存股
    '00930.TW': 0.69,        # 永豐 ESG 低碳高息
    '00701.TW': 0.49,        # 國泰股利精選30
    '00730.TW': 0.61,        # 富邦臺灣優質高息
    '00702.TW': 0.54,        # 國泰標普低波高息
    
    # 產業型 ETF
    '00891.TW': 0.67,        # 中信關鍵半導體
    '00892.TW': 0.65,        # 富邦台灣半導體
    '00927.TW': 0.80,        # 群益半導體收益
    '00947.TW': 0.78,        # 台新臺灣 IC 設計動能
    '00904.TW': 0.75,        # 新光臺灣半導體
    '00941.TW': 0.72,        # 中信上游半導體
    '00757.TW': 1.15,        # 統一 FANG＋
    '0052.TW': 0.20,         # 富邦台灣科技
    '00881.TW': 0.81,        # 國泰台灣 5G+
    '00935.TW': 0.85,        # 野村台灣創新科技 50
    '00861.TW': 0.76,        # 元大全球未來通訊
    '00896.TW': 0.77,        # 中信綠能及電動車
    '00893.TW': 0.73,        # 國泰全球智能電動車
    '00895.TW': 0.74,        # 富邦未來車
    '00925.TW': 0.68,        # 新光標普電動車
    '0055.TW': 0.30,         # 元大 MSCI 台灣金融
    '00921.TW': 0.69,        # 兆豐龍頭等權重
    '00937B.TW': 0.85,       # 群益 ESG 投等債 20+
}


def try_fetch_from_yfinance(ticker):
    """嘗試從 Yahoo Finance 獲取費用率"""
    try:
        etf = yf.Ticker(ticker)
        info = etf.info
        
        if 'expenseRatio' in info:
            return info['expenseRatio'] * 100  # 轉換為百分比
        
        if 'trailingExpenseRatio' in info:
            return info['trailingExpenseRatio'] * 100
        
    except Exception as e:
        print(f"   ⚠️  {ticker} Yahoo Finance 查詢失敗: {type(e).__name__}")
    
    return None


def load_config(config_type='active_etf'):
    """加載配置文件"""
    config_path = os.path.join('etf_configs', f'{config_type}.json')
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 加載配置失敗: {e}")
        return None


def save_config(config, config_type='active_etf'):
    """保存配置文件"""
    config_path = os.path.join('etf_configs', f'{config_type}.json')
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"✅ 配置已保存到 {config_path}")
        return True
    except Exception as e:
        print(f"❌ 保存配置失敗: {e}")
        return False


def update_expense_ratio(config_type='active_etf', use_yfinance=True):
    """更新費用率"""
    print(f"\n{'='*70}")
    print(f"ETF 費用率更新工具 - {config_type}")
    print(f"{'='*70}\n")
    
    # 加載配置
    config = load_config(config_type)
    if not config:
        print("❌ 無法加載配置")
        return False
    
    # 獲取 ETF 列表
    etf_list = config.get('etf_list', [])
    print(f"📊 配置中包含 {len(etf_list)} 支 ETF")
    
    # 初始化 expense_ratio（如果不存在）
    if 'expense_ratio' not in config:
        config['expense_ratio'] = {}
    
    print(f"\n{'='*70}")
    print("開始更新費用率:")
    print(f"{'='*70}\n")
    
    updated_count = 0
    failed_count = 0
    
    for ticker, name in etf_list:
        ticker_clean = ticker.strip()
        name_clean = name.strip()
        
        old_value = config['expense_ratio'].get(ticker_clean)
        new_value = None
        source = None
        
        # 1. 先嘗試已知數據庫
        if ticker_clean in KNOWN_EXPENSE_RATIOS:
            new_value = KNOWN_EXPENSE_RATIOS[ticker_clean]
            source = "本地數據庫"
        
        # 2. 如果啟用了 Yahoo Finance，嘗試獲取最新數據
        if use_yfinance and new_value is None:
            print(f"  🔍 {ticker_clean} ({name_clean})...", end=" ")
            yf_value = try_fetch_from_yfinance(ticker_clean)
            if yf_value is not None:
                new_value = round(yf_value, 3)
                source = "Yahoo Finance"
                print(f"✅ {new_value}%")
            else:
                print("查詢失敗")
        
        # 3. 顯示結果
        if new_value is not None:
            config['expense_ratio'][ticker_clean] = new_value
            
            if old_value is None:
                print(f"  ✅ {ticker_clean} ({name_clean})")
                print(f"     新增: {new_value}% (來源: {source})")
                updated_count += 1
            elif old_value != new_value:
                print(f"  ✅ {ticker_clean} ({name_clean})")
                print(f"     {old_value}% → {new_value}% (來源: {source})")
                updated_count += 1
            else:
                print(f"  ➜ {ticker_clean} ({name_clean}): {new_value}% (無變化)")
        else:
            print(f"  ⚠️  {ticker_clean} ({name_clean}): 未找到費用率")
            # 保留現有值或設置為 null
            if ticker_clean not in config['expense_ratio']:
                config['expense_ratio'][ticker_clean] = None
            failed_count += 1
    
    # 保存更新後的配置
    print(f"\n{'='*70}")
    if save_config(config, config_type):
        print(f"✅ 成功更新 {updated_count} 支 ETF 的費用率")
        if failed_count > 0:
            print(f"⚠️  {failed_count} 支 ETF 未找到費用率數據 (設置為 null)")
        return True
    else:
        print("❌ 保存失敗")
        return False


def list_known_expense_ratios():
    """列出已知的費用率數據"""
    print(f"\n{'='*70}")
    print("已知的 ETF 費用率數據庫")
    print(f"{'='*70}\n")
    
    for ticker, ratio in sorted(KNOWN_EXPENSE_RATIOS.items()):
        print(f"  {ticker}: {ratio}%")
    
    print(f"\n共 {len(KNOWN_EXPENSE_RATIOS)} 支 ETF\n")


if __name__ == '__main__':
    import sys
    
    # 解析命令行參數
    config_type = 'active_etf'
    use_yfinance = True
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--list':
            list_known_expense_ratios()
            sys.exit(0)
        else:
            config_type = sys.argv[1]
    
    if '--no-yfinance' in sys.argv:
        use_yfinance = False
        print("⚠️  已禁用 Yahoo Finance 查詢，只使用本地數據")
    
    update_expense_ratio(config_type, use_yfinance=use_yfinance)

