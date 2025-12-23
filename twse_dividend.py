from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import time
from webdriver_manager.chrome import ChromeDriverManager


def convert_roc_date(roc_date_str):
    """將民國年日期轉換為西元年日期，例如 '113年06月17日' 轉為 '2024-06-17'"""
    try:
        if not roc_date_str or '年' not in roc_date_str or '月' not in roc_date_str or '日' not in roc_date_str:
            return None
        roc_year, month_day = roc_date_str.split('年')
        month, day = month_day.split('月')
        day = day.split('日')[0]
        gregorian_year = int(roc_year) + 1911
        return f"{gregorian_year}-{month.zfill(2)}-{day.zfill(2)}"
    except Exception as e:
        print(f"日期轉換失敗：{e}，原始內容：{roc_date_str}")
        return None

def get_twse_dividend_data(ticker, name, start_date, end_date):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
    from bs4 import BeautifulSoup
    import numpy as np
    from datetime import datetime

    etf_id = ticker.replace('.TW', '')
    url = f"https://www.twse.com.tw/zh/products/securities/etf/products/div.html?etf_id={etf_id}"

    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--log-level=3')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    try:
        driver.get(url)
        # 等待查詢按鈕出現並點擊
        try:
            search_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.search"))
            )
            search_btn.click()
        except Exception as e:
            print("查詢按鈕點擊失敗", e)
            return {
                '證券代碼': ticker,
                '名稱': name,
                '配息頻率': 'N/A',
                '平均配息金額 (台幣/單位)': 'N/A'
            }

        # 等待表格資料載入
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".rwd-table tr"))
            )
        except Exception as e:
            print("配息表格載入失敗", e)
            return {
                '證券代碼': ticker,
                '名稱': name,
                '配息頻率': 'N/A',
                '平均配息金額 (台幣/單位)': 'N/A'
            }

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        table_div = soup.find('div', class_='rwd-table')
        rows = table_div.find_all('tr') if table_div else []
        dividends = []
        for row in rows[1:]:
            cols = row.find_all('td')
            if len(cols) < 5:
                continue
            ex_div_date_str = cols[1].text.strip()
            ex_div_date = convert_roc_date(ex_div_date_str)
            if ex_div_date and start_date <= ex_div_date <= end_date:
                try:
                    dividend_amount = float(cols[4].text.strip())
                except Exception:
                    dividend_amount = 0
                dividends.append({
                    '除息交易日': ex_div_date,
                    '收益分配金額 (每1受益權益單位)': dividend_amount
                })

        if not dividends:
            return {
                '證券代碼': ticker,
                '名稱': name,
                '配息頻率': 'N/A',
                '平均配息金額 (台幣/單位)': 'N/A'
            }

        dates = [datetime.strptime(d['除息交易日'], '%Y-%m-%d') for d in dividends]
        dates.sort()
        if len(dates) < 2:
            frequency = '不確定（數據不足）'
        else:
            intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
            avg_interval = np.mean(intervals)
            if avg_interval < 45:
                frequency = '月配'
            elif avg_interval < 135:
                frequency = '季配'
            elif avg_interval < 270:
                frequency = '半年度'
            else:
                frequency = '年配'
        avg_dividend = round(np.mean([d['收益分配金額 (每1受益權益單位)'] for d in dividends]), 4)

        return {
            '證券代碼': ticker,
            '名稱': name,
            '配息頻率': frequency,
            '平均配息金額 (台幣/單位)': avg_dividend
        }
    finally:
        driver.quit()