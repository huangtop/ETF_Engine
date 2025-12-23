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

def load_twse_dividend_table():
    global _twse_dividend_df
    if _twse_dividend_df is None:
        url = "https://www.twse.com.tw/zh/ETFortune/dividendList"
        driver = webdriver.Chrome()
        driver.get(url)
        time.sleep(5)
        table = driver.find_element(By.ID, "myTable")
        html = table.get_attribute('outerHTML')
        driver.quit()
        # df = pd.read_html(html)[0]
        from io import StringIO
        df = pd.read_html(StringIO(html))[0]
        df['證券代號'] = df['證券代號'].astype(str)
        df['除息交易日'] = df['除息交易日'].apply(roc_to_ad)
        df['除息交易日'] = pd.to_datetime(df['除息交易日'], errors='coerce')
        _twse_dividend_df = df
    return _twse_dividend_df

def get_twse_dividend(stock_id):
    df = load_twse_dividend_table()
    stock_id = str(stock_id)
    df_etf = df[df['證券代號'] == stock_id].copy()
    if df_etf.empty:
        print(f"找不到 {stock_id} 配息資料")
    return df_etf

if __name__ == "__main__":
    print(get_twse_dividend("0056"))
    print(get_twse_dividend("00919"))