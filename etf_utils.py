"""ETF 配置和标签处理的辅助函数"""


def normalize_etf_item(item):
    """正規化 ETF 列表項，支持數組和對象格式
    
    參數:
        item: ETF 列表項，可以是 [ticker, name]、[ticker, name, type] 或對象格式
    
    返回:
        (ticker, name, etf_type, short_name) 的元組
    """
    if isinstance(item, dict):
        # 對象格式
        ticker = item.get('ticker', '')
        name = item.get('name', '')
        etf_type = item.get('type', '')
        short_name = item.get('short_name', name)
        return ticker, name, etf_type, short_name
    else:
        # 數組格式 [ticker, name] 或 [ticker, name, type]
        ticker = item[0] if len(item) > 0 else ''
        name = item[1] if len(item) > 1 else ''
        etf_type = item[2] if len(item) > 2 else ''
        short_name = name  # 數組格式沒有 short_name，使用完整名稱
        return ticker, name, etf_type, short_name


def smart_label_with_ticker(name, ticker, short_name=None):
    """智能標籤處理，使用 short_name 或從 name 推導
    
    參數:
        name: ETF 完整名稱
        ticker: ETF 代碼
        short_name: 簡短名稱（可選，來自 JSON 配置）
    
    如果提供了 short_name，直接使用；否則從 name 推導
    """
    if short_name:
        # 優先使用配置中的 short_name
        ticker_short = ticker.replace('.TW', '').strip()
        return f"{ticker_short}\n{short_name}"
    
    # 後備：從 name 推導（主要用於舊配置）
    name = name.strip()
    ticker_short = ticker.replace('.TW', '').strip()
    
    # 簡化名稱但保留關鍵資訊
    if '主動' in name:
        # 主動型：保留"主動"標識，移除"台灣"節省空間
        short_name = name.replace('台灣', '').strip()
        return f"{ticker_short}\n{short_name}"
    elif 'ARK' in name:
        return f"{ticker_short}\nARK創新"
    elif 'S&P500' in name:
        return f"{ticker_short}\nS&P500"
    elif 'NASDAQ' in name:
        return f"{ticker_short}\nNASDAQ"
    elif 'FANG' in name:
        return f"{ticker_short}\nFANG+"
    elif '台灣50' in name or '台50' in name:
        return f"{ticker_short}\n台灣50"
    elif '高股息' in name:
        base_name = name.replace('高股息', '').strip()
        return f"{ticker_short}\n{base_name}高息"
    elif '永續' in name:
        return f"{ticker_short}\n永續高息"
    else:
        if len(name) > 8:
            short_name = name[:6] + '..'
            return f"{ticker_short}\n{short_name}"
        return f"{ticker_short}\n{name}"
