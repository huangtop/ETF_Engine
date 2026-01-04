"""
股價資料獲取模組
使用 TWSE（台股）和 Alpha Vantage（美股）作為資料來源
包含智能快取機制，避免重複調用 API
"""

import pandas as pd
import requests
import os
import json
from datetime import datetime, timedelta
import time

# Alpha Vantage API key（從環境變數讀取，不寫到程式中）
ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY', 'demo')

# 快取設定
CACHE_DIR = 'cache'
CACHE_FILE = os.path.join(CACHE_DIR, 'alpha_vantage_cache.json')
CACHE_VALIDITY_DAYS = 7  # 快取有效期（天）

# 確保快取目錄存在
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)
    print(f"✅ 創建快取目錄: {CACHE_DIR}")


def load_cache():
    """從 JSON 檔案讀取快取"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            print(f"✅ 載入快取: {CACHE_FILE}")
            return cache
        except Exception as e:
            print(f"⚠️  快取讀取失敗: {e}，將重新獲取資料")
            return {}
    return {}


def save_cache(cache):
    """將快取寫入 JSON 檔案"""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
        print(f"✅ 快取已保存: {CACHE_FILE}")
    except Exception as e:
        print(f"⚠️  快取保存失敗: {e}")


def is_cache_valid(cached_item):
    """檢查快取是否仍有效"""
    if 'timestamp' not in cached_item:
        return False
    
    cached_time = datetime.fromisoformat(cached_item['timestamp'])
    now = datetime.now()
    days_old = (now - cached_time).days
    
    return days_old < CACHE_VALIDITY_DAYS


def fetch_twse_price(ticker, start_date, end_date):
    """
    從 TWSE 官方 REST API 抓取台股 ETF 股價
    完全使用官方 API，不依賴任何第三方金融服務
    
    Args:
        ticker: 股票代碼（如 '0050.TW' 或 '0050'）
        start_date: 起始日期 (YYYY-MM-DD)
        end_date: 結束日期 (YYYY-MM-DD)
    
    Returns:
        pd.DataFrame: OHLCV 資料，index 為日期
    """
    
    # 移除 .TW 後綴
    ticker_clean = ticker.replace('.TW', '').strip()
    
    try:
        print(f"  📥 從 TWSE 官方 API 下載 {ticker} 股價...")
        
        all_data = []
        start_date_dt = pd.to_datetime(start_date)
        end_date_dt = pd.to_datetime(end_date)
        current_date = start_date_dt
        
        # TWSE API 採用月份查詢，需要逐月遍歷
        while current_date <= end_date_dt:
            year = current_date.year
            month = current_date.month
            
            # TWSE API 格式: YYYYMMDD (西元年)
            query_date = f"{year}{month:02d}01"
            
            url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
            params = {
                'response': 'json',
                'date': query_date,
                'stockNo': ticker_clean
            }
            
            try:
                response = requests.get(url, params=params, timeout=10, verify=False)
                data = response.json()
                
                if data.get('data'):
                    for row in data['data']:
                        try:
                            date_str = row[0]  # 格式: 民國年/月/日 (e.g., 115/01/02)
                            
                            # 轉換民國年份為西元年
                            parts = date_str.split('/')
                            roc_year = int(parts[0])
                            gregorian_year = roc_year + 1911  # 民國 + 1911 = 西元
                            gregorian_date_str = f"{gregorian_year}/{parts[1]}/{parts[2]}"
                            
                            date = pd.to_datetime(gregorian_date_str)
                            
                            if start_date_dt <= date <= end_date_dt:
                                all_data.append({
                                    'Date': date,
                                    'Open': float(row[3].replace(',', '')),      # 開盤價
                                    'High': float(row[4].replace(',', '')),      # 最高價
                                    'Low': float(row[5].replace(',', '')),       # 最低價
                                    'Close': float(row[6].replace(',', '')),     # 收盤價
                                    'Volume': int(row[1].replace(',', ''))       # 成交股數
                                })
                        except (ValueError, IndexError) as e:
                            continue
                
            except requests.exceptions.RequestException as e:
                pass  # 某些月份可能無資料或 API 無反應，繼續下一個月
            
            # 移到下一個月
            if month == 12:
                current_date = pd.to_datetime(f"{year+1}-01-01")
            else:
                current_date = pd.to_datetime(f"{year}-{month+1:02d}-01")
        
        if all_data:
            df = pd.DataFrame(all_data)
            df.set_index('Date', inplace=True)
            df = df.sort_index()
            
            print(f"  ✅ 獲取 {ticker} {len(df)} 天資料（TWSE 官方 API）")
            return df
        else:
            print(f"  ❌ {ticker} 無資料")
            return pd.DataFrame()
            
    except Exception as e:
        print(f"  ❌ {ticker} 下載失敗: {e}")
        return pd.DataFrame()


def fetch_us_stock_price(symbol, start_date, end_date, api_key=None):
    """
    從 Alpha Vantage 抓取美股股價（優先使用快取）
    
    Args:
        symbol: 股票代碼（如 'VOO', 'GSPC'）
        start_date: 起始日期 (YYYY-MM-DD)
        end_date: 結束日期 (YYYY-MM-DD)
        api_key: Alpha Vantage API key（若為 None 則使用預設）
    
    Returns:
        pd.DataFrame: OHLCV 資料，index 為日期
    """
    
    if api_key is None:
        api_key = ALPHA_VANTAGE_API_KEY
    
    # 移除指數符號前綴
    if symbol.startswith('^'):
        symbol = symbol[1:]  # 移除 ^
    
    # 檢查快取
    cache = load_cache()
    cache_key = f"av_{symbol}"
    
    if cache_key in cache:
        cached_item = cache[cache_key]
        if is_cache_valid(cached_item):
            print(f"  ♻️  從快取讀取 {symbol} 股價...")
            try:
                # 從快取恢復 DataFrame
                df_data = cached_item['data']
                df = pd.DataFrame(df_data)
                df['Date'] = pd.to_datetime(df['Date'])
                df.set_index('Date', inplace=True)
                
                # 篩選日期範圍
                start = pd.to_datetime(start_date)
                end = pd.to_datetime(end_date)
                df = df[(df.index >= start) & (df.index <= end)]
                
                print(f"  ✅ 從快取獲取 {symbol} {len(df)} 天資料")
                return df
            except Exception as e:
                print(f"  ⚠️  快取恢復失敗: {e}，重新獲取...")
    
    # 快取失效或不存在，從 API 獲取
    try:
        print(f"  📥 從 Alpha Vantage 下載 {symbol} 股價...")
        
        url = "https://www.alphavantage.co/query"
        params = {
            'function': 'TIME_SERIES_DAILY',
            'symbol': symbol,
            'outputsize': 'full',
            'apikey': api_key
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        # 檢查 API 錯誤
        if 'Error Message' in data:
            print(f"  ❌ {symbol} API 錯誤: {data['Error Message']}")
            return pd.DataFrame()
        
        if 'Note' in data:
            print(f"  ⚠️  {symbol} API 限制: {data['Note']}")
            return pd.DataFrame()
        
        if 'Time Series (Daily)' not in data:
            print(f"  ❌ {symbol} 無法從 Alpha Vantage 獲取資料（可能是無效代碼或 API 額度用盡）")
            print(f"     回應: {list(data.keys())[:3]}")
            return pd.DataFrame()
        
        # 轉換為 DataFrame
        time_series = data['Time Series (Daily)']
        df_list = []
        
        for date_str, values in time_series.items():
            try:
                df_list.append({
                    'Date': date_str,
                    'Open': float(values['1. open']),
                    'High': float(values['2. high']),
                    'Low': float(values['3. low']),
                    'Close': float(values['4. close']),
                    'Volume': int(float(values['5. volume']))
                })
            except (KeyError, ValueError):
                continue
        
        if not df_list:
            print(f"  ❌ {symbol} 無法解析資料")
            return pd.DataFrame()
        
        df = pd.DataFrame(df_list)
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        df = df.sort_index()
        
        # 保存到快取
        cache[cache_key] = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'data': df.reset_index().to_dict('records')  # 轉換為可序列化格式
        }
        save_cache(cache)
        
        # 篩選日期範圍
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        df = df[(df.index >= start) & (df.index <= end)]
        
        print(f"  ✅ 獲取 {symbol} {len(df)} 天資料（已快取）")
        return df
        
    except requests.exceptions.Timeout:
        print(f"  ❌ {symbol} 下載逾時（API 反應緩慢）")
        return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        print(f"  ❌ {symbol} 網路錯誤: {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"  ❌ {symbol} 下載失敗: {e}")
        return pd.DataFrame()


def is_us_stock(ticker):
    """
    判斷是否為美國本土股票（需用 Alpha Vantage）
    
    Args:
        ticker: 股票代碼
    
    Returns:
        bool: True 表示美股，False 表示台股
    """
    # 美股指數和本土 ETF
    us_symbols = ['^GSPC', 'GSPC', 'VOO']
    
    return ticker.upper() in us_symbols or (not ticker.endswith('.TW') and not ticker.isdigit())


def download_price_data(ticker, start_date, end_date, api_key=None):
    """
    統一的股價下載函數
    自動判斷是台股還是美股，使用對應的資料來源
    
    Args:
        ticker: 股票代碼
        start_date: 起始日期 (YYYY-MM-DD)
        end_date: 結束日期 (YYYY-MM-DD)
        api_key: Alpha Vantage API key（選擇性）
    
    Returns:
        pd.DataFrame: OHLCV 資料
    """
    
    if is_us_stock(ticker):
        # 美股或指數 → Alpha Vantage
        return fetch_us_stock_price(ticker, start_date, end_date, api_key)
    else:
        # 台股 → TWSE
        return fetch_twse_price(ticker, start_date, end_date)


def set_alpha_vantage_key(api_key):
    """
    設定 Alpha Vantage API key
    
    Args:
        api_key: 你的 Alpha Vantage API key
    """
    global ALPHA_VANTAGE_API_KEY
    ALPHA_VANTAGE_API_KEY = api_key
    print(f"✅ Alpha Vantage API key 已設定")


def clear_cache():
    """清除所有快取"""
    try:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
            print(f"✅ 快取已清除: {CACHE_FILE}")
    except Exception as e:
        print(f"❌ 快取清除失敗: {e}")


def clear_cache_item(symbol):
    """清除特定股票的快取"""
    cache = load_cache()
    cache_key = f"av_{symbol}"
    if cache_key in cache:
        del cache[cache_key]
        save_cache(cache)
        print(f"✅ 已清除 {symbol} 的快取")
    else:
        print(f"⚠️  {symbol} 無快取")


