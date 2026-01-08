import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import re

def roc_to_ad(date_str):
    if isinstance(date_str, str):
        m = re.match(r"(\d{2,3})年(\d{1,2})月(\d{1,2})日", date_str.strip())
        if m:
            year = int(m.group(1))
            if year < 1911:
                year += 1911
            return f"{year}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
        m = re.match(r"(\d{2,3})/(\d{1,2})/(\d{1,2})", date_str.strip())
        if m:
            year = int(m.group(1))
            if year < 1911:
                year += 1911
            return f"{year}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return None

# 全域快取 DataFrame
_twse_dividend_df = None

def load_twse_dividend_table(year=2025):  # 預設爬取2025年資料
    """載入TWSE配息表格
    Args:
        year: 西元年 (2025, 2024, 2023...)
    """
    global _twse_dividend_df
    if _twse_dividend_df is None:
        # 使用正確的URL參數格式
        url = f"https://www.twse.com.tw/zh/ETFortune/dividendList?stkNo=&startDate={year}&endDate={year}"
        driver = webdriver.Chrome()
        driver.get(url)
        print(f"等待網頁載入... (查詢{year}年配息資料)")
        time.sleep(5)
        
        # 調試：查看網頁內容
        print("查找表格元素...")
        try:
            # 嘗試多種可能的表格選擇器
            table = None
            selectors = [
                "myTable",           # 原始 ID
                "table",             # 任何表格
                ".table",            # class="table"
                "#dividend-table",   # 可能的新 ID
                "tbody",             # 表格主體
                ".rwd-table"         # 響應式表格
            ]
            
            for selector in selectors:
                try:
                    if selector.startswith('#') or selector.startswith('.'):
                        table = driver.find_element(By.CSS_SELECTOR, selector)
                    elif selector == "table" or selector == "tbody":
                        table = driver.find_element(By.TAG_NAME, selector)
                    else:
                        table = driver.find_element(By.ID, selector)
                    print(f"✅ 找到表格：{selector}")
                    break
                except:
                    print(f"❌ 找不到：{selector}")
                    continue
            
            if table is None:
                # 如果都找不到，顯示網頁源碼片段
                print("所有選擇器都失敗，顯示網頁內容片段：")
                print(driver.page_source[:2000])
                driver.quit()
                return None
            
            html = table.get_attribute('outerHTML')
            driver.quit()
            
            # df = pd.read_html(html)[0]
            from io import StringIO
            df = pd.read_html(StringIO(html))[0]
            print(f"✅ 成功解析表格，共 {len(df)} 行")
            print("前5行數據：")
            print(df.head())
            
            df['證券代號'] = df['證券代號'].astype(str)
            df['除息交易日'] = df['除息交易日'].apply(roc_to_ad)
            df['除息交易日'] = pd.to_datetime(df['除息交易日'], errors='coerce')
            _twse_dividend_df = df
        except Exception as e:
            print(f"❌ 解析失敗：{e}")
            driver.quit()
            return None
            
    return _twse_dividend_df

def get_twse_dividend(stock_id, year=2025):
    """獲取指定ETF的配息資料
    Args:
        stock_id: 股票代號 (如 '0056')
        year: 西元年 (2025, 2024, 2023...)
    """
    df = load_twse_dividend_table(year)
    if df is None:
        print(f"❌ 無法載入{year}年股息表格")
        return pd.DataFrame()
        
    stock_id = str(stock_id)
    df_etf = df[df['證券代號'] == stock_id].copy()
    if df_etf.empty:
        print(f"找不到 {stock_id} {year}年配息資料")
    else:
        print(f"✅ 找到 {stock_id} {year}年配息資料: {len(df_etf)} 筆")
    return df_etf

if __name__ == "__main__":
    print(get_twse_dividend("0056"))
    print(get_twse_dividend("00919"))