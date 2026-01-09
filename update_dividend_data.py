#!/usr/bin/env python3
"""
更新高股息ETF的2025年配息資訊
使用 twse_dividend.py 爬取實際配息數據並更新到 JSON 配置文件
"""

import json
import pandas as pd
from twse_dividend import get_twse_dividend
import time

def load_etf_config():
    """載入高股息ETF配置"""
    with open('etf_configs/high_dividend_etf.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def save_etf_config(config):
    """儲存更新後的ETF配置"""
    with open('etf_configs/high_dividend_etf.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def get_etf_dividend_data(ticker, year=2025):
    """
    獲取單個ETF的配息資料
    
    Args:
        ticker: ETF代碼 (如 '0056.TW')
        year: 年度 (2025)
    
    Returns:
        dict: 包含總配息金額和配息次數
    """
    # 清除 .TW 後綴用於查詢
    clean_ticker = ticker.replace('.TW', '')
    
    try:
        print(f"📊 查詢 {ticker} ({clean_ticker}) {year}年配息資料...")
        df = get_twse_dividend(clean_ticker, year)
        
        if df.empty:
            print(f"  ❌ 沒有找到 {ticker} {year}年配息資料")
            return {"total_dividend": 0.0, "dividend_count": 0}
        
        # 計算總配息金額和次數
        dividend_amounts = []
        for _, row in df.iterrows():
            amount = row.get('收益分配金額 (每1受益權益單位)', 0)
            if pd.notna(amount) and amount != 'NaN' and amount != '':
                try:
                    dividend_amounts.append(float(amount))
                except (ValueError, TypeError):
                    continue
        
        total_dividend = sum(dividend_amounts)
        dividend_count = len(dividend_amounts)
        
        print(f"  ✅ {ticker}: 配息 {dividend_count} 次，總金額 {total_dividend:.3f}元")
        if dividend_count > 0:
            print(f"     各次配息: {dividend_amounts}")
        
        return {
            "total_dividend": round(total_dividend, 3),
            "dividend_count": dividend_count
        }
        
    except Exception as e:
        print(f"  ❌ {ticker} 查詢失敗: {e}")
        return {"total_dividend": 0.0, "dividend_count": 0}

def main():
    """主要執行函數"""
    print("🚀 開始更新高股息ETF的2025年配息資訊...")
    
    # 載入配置
    config = load_etf_config()
    
    # 初始化配息數據結構
    if "dividend_2025" not in config:
        config["dividend_2025"] = {}
    
    if "dividend_frequency" not in config:
        config["dividend_frequency"] = {}
    
    # 獲取所有ETF列表
    etf_list = config.get("etf_list", [])
    total_etfs = len(etf_list)
    
    print(f"📋 總共需要查詢 {total_etfs} 支高股息ETF")
    print("-" * 60)
    
    # 逐一查詢每支ETF
    successful_updates = 0
    failed_updates = 0
    
    for i, etf in enumerate(etf_list, 1):
        ticker = etf["ticker"]
        name = etf["name"]
        
        print(f"\n[{i}/{total_etfs}] 處理 {ticker} - {name}")
        
        # 獲取配息數據
        dividend_data = get_etf_dividend_data(ticker, 2025)
        
        # 更新配置
        config["dividend_2025"][ticker] = dividend_data["total_dividend"]
        config["dividend_frequency"][ticker] = dividend_data["dividend_count"]
        
        if dividend_data["dividend_count"] > 0:
            successful_updates += 1
        else:
            failed_updates += 1
        
        # 避免過於頻繁的請求
        if i < total_etfs:  # 最後一個不需要等待
            time.sleep(2)
    
    # 更新 metadata
    config["metadata"]["dividend_data_updated"] = "2025-data-crawled"
    config["metadata"]["dividend_crawl_date"] = "2026-01-09"
    
    # 儲存更新後的配置
    save_etf_config(config)
    
    print("\n" + "=" * 60)
    print("📊 配息資訊更新完成！")
    print(f"✅ 成功更新: {successful_updates} 支ETF")
    print(f"❌ 無配息數據: {failed_updates} 支ETF")
    print(f"📁 已儲存到: etf_configs/high_dividend_etf.json")
    print("=" * 60)
    
    # 顯示統計摘要
    print("\n📈 2025年配息統計摘要:")
    successful_etfs = []
    for etf in etf_list:
        ticker = etf["ticker"]
        if config["dividend_frequency"].get(ticker, 0) > 0:
            dividend = config["dividend_2025"].get(ticker, 0)
            frequency = config["dividend_frequency"].get(ticker, 0)
            successful_etfs.append({
                "ticker": ticker,
                "name": etf["name"],
                "dividend": dividend,
                "frequency": frequency
            })
    
    # 按配息金額排序
    successful_etfs.sort(key=lambda x: x["dividend"], reverse=True)
    
    print("\n🏆 TOP 10 配息ETF (2025年):")
    for i, etf in enumerate(successful_etfs[:10], 1):
        print(f"{i:2d}. {etf['ticker']:<10} {etf['name']:<20} "
              f"配息: {etf['dividend']:.3f}元 (共{etf['frequency']}次)")

if __name__ == "__main__":
    main()
