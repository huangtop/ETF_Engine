import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.font_manager import FontProperties
import platform
from data_fetcher import download_price_data, set_alpha_vantage_key
import os
import sys
import warnings
import signal

# 抑制警告
warnings.filterwarnings('ignore')

# 超時處理：30 分鐘（足以下載和分析多個 ETF）
def timeout_handler(signum, frame):
    print("\n❌ 程式執行超時（30 分鐘），強制退出")
    sys.exit(1)

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(1800)  # 30 分鐘

# 設定環境變數，避免 tkinter 衝突
os.environ['MPLBACKEND'] = 'Agg'

# 確保 matplotlib 使用正確後端
import matplotlib
matplotlib.use('Agg', force=True)

import matplotlib.pyplot as plt
plt.ioff()  # 關閉互動模式

# 導入改進的字體配置
from font_config import setup_chinese_font_enhanced, update_font_sizes, FONT_SIZE_CONFIG

# 設置中文字體和字體大小
setup_chinese_font_enhanced()
update_font_sizes()

# 從 JSON 配置加載 ETF 列表
from config_loader import load_etf_config

# 從命令行獲取配置類型，默認為 'active_etf'
if len(sys.argv) > 1:
    config_type = sys.argv[1]
else:
    config_type = 'active_etf'

print(f"📋 使用配置: {config_type}")

# 加载配置
config = load_etf_config(config_type)
etf_list = config['etf_list']
expense_ratio_dict = config['expense_ratio']

# 根據配置類型設置文件名前綴，避免不同ETF類型覆蓋
if config_type == 'active_etf':
    etf_type_prefix = 'Active_'
elif config_type == 'high_dividend_etf':
    etf_type_prefix = 'HighDividend_'
elif config_type == 'industry_etf':
    etf_type_prefix = 'Industry_'
else:
    etf_type_prefix = ''

# 風險無風報酬率
risk_free_rate = 0.015

# 日期範圍
today = datetime.now()
start_date_3y = (today - timedelta(days=3*365)).strftime('%Y-%m-%d')
latest_date = today.strftime('%Y-%m-%d')

# 對主動式 ETF 使用固定的起始日期（2025-07-22）
# 因為主動式 ETF 很多最近才上市，數據不足
if config_type == 'active_etf':
    start_date_3y = '2025-07-22'
    print(f"⚠️  主動式 ETF 使用固定起始日期: {start_date_3y}")
def get_output_folder(config_type='active_etf'):
    """根據配置類型創建對應的輸出資料夾"""
    folder_mapping = {
        'active_etf': 'Output_Active_ETF',
        'dividend_etf': 'Output_Dividend_ETF',
        'high_dividend_etf': 'Output_HighDividend_ETF',
        'us_etf': 'Output_US_ETF',
        'industry_etf': 'Output_Industry_ETF'
    }
    
    folder_name = folder_mapping.get(config_type, 'Output_Default')
    output_path = os.path.join(os.getcwd(), folder_name)
    
    # 如果資料夾不存在則創建
    if not os.path.exists(output_path):
        os.makedirs(output_path)
        print(f"✅ 創建輸出資料夾: {output_path}")
    
    return output_path


# 初始化輸出資料夾
output_folder = get_output_folder(config_type)


def smart_label_with_ticker(name, ticker):
    """智能標籤處理，保留股票代號和關鍵資訊"""
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
        # 其他情況：如果名稱太長，適度縮短
        if len(name) > 8:
            short_name = name[:6] + '..'
            return f"{ticker_short}\n{short_name}"
        return f"{ticker_short}\n{name}"

def find_common_start_date(etf_list, initial_start_date, end_date, use_fixed_start=False):
    """找出所有ETF的最晚開始日期作為統一比較期間
    
    Args:
        etf_list: ETF 列表（支持對象和數組格式）
        initial_start_date: 初始起始日期
        end_date: 結束日期
        use_fixed_start: 是否使用固定的起始日期（跳過太新的ETF）
    """
    latest_start_date = None
    
    print("\n📅 檢查各ETF資料起始日期...")
    for item in etf_list:
        # 支持對象和數組兩種格式
        if isinstance(item, dict):
            ticker = item.get('ticker', '').strip()
            name = item.get('name', '').strip()
        else:
            ticker = item[0].strip()
            name = item[1].strip()
        
        if not ticker:
            continue
            
        try:
            df = download_price_data(ticker, start_date=initial_start_date, end_date=end_date)
            if isinstance(df, pd.DataFrame) and not df.empty:
                df.dropna(inplace=True)
                if len(df) > 0:
                    etf_start = df.index[0]
                    print(f"  {ticker}: 資料開始於 {etf_start.strftime('%Y-%m-%d')}")
                    
                    # 如果使用固定起始日期，只記錄不早於起始日期的 ETF
                    if use_fixed_start:
                        if etf_start <= pd.to_datetime(initial_start_date):
                            if latest_start_date is None or etf_start > latest_start_date:
                                latest_start_date = etf_start
                    else:
                        if latest_start_date is None or etf_start > latest_start_date:
                            latest_start_date = etf_start
        except Exception as e:
            print(f"  {ticker} 檢查失敗: {type(e).__name__}")
    
    if use_fixed_start:
        # 對於主動式 ETF，強制使用指定的起始日期
        common_start = initial_start_date
        print(f"\n📊 統一比較期間: {common_start} 至 {end_date}")
        return common_start
    elif latest_start_date:
        common_start = latest_start_date.strftime('%Y-%m-%d')
        print(f"\n📊 統一比較期間: {common_start} 至 {end_date}")
        return common_start
    else:
        return initial_start_date

def calculate_returns(prices, annualize=True):
    """計算報酬率
    
    Args:
        prices: 價格序列
        annualize: 是否進行年化（True=年化報酬率，False=實際報酬率）
    
    Returns:
        (報酬率, 年數)
    """
    try:
        if len(prices) < 2:
            return np.nan, np.nan
        
        if isinstance(prices, pd.DataFrame):
            prices = prices.iloc[:, 0]
            
        start_price = prices.iloc[0]
        end_price = prices.iloc[-1]
        
        if isinstance(start_price, pd.Series):
            start_price = start_price.iloc[0]
        if isinstance(end_price, pd.Series):
            end_price = end_price.iloc[0]
            
        years = len(prices) / 252
        total_return = (end_price / start_price) - 1
        
        if annualize and years >= 1.0:
            # 年化報酬率
            cagr = (end_price / start_price) ** (1 / years) - 1
            return cagr, years
        else:
            # 實際報酬率（不年化）
            return total_return, years
            
    except Exception as e:
        print(f"報酬率計算錯誤: {e}")
        return np.nan, np.nan


def calculate_period_returns(prices, period_days=252):
    """計算特定期間的年化報酬率
    
    Args:
        prices: 價格序列
        period_days: 期間天數（252=1年，756=3年）
    
    Returns:
        (年化報酬率, 實際天數)
    """
    try:
        if len(prices) < period_days:
            return np.nan, len(prices)
        
        if isinstance(prices, pd.DataFrame):
            prices = prices.iloc[:, 0]
        
        # 取最後 period_days 個交易日
        period_prices = prices.iloc[-period_days:]
        start_price = period_prices.iloc[0]
        end_price = period_prices.iloc[-1]
        
        if isinstance(start_price, pd.Series):
            start_price = start_price.iloc[0]
        if isinstance(end_price, pd.Series):
            end_price = end_price.iloc[0]
        
        years = len(period_prices) / 252
        cagr = (end_price / start_price) ** (1 / years) - 1
        
        return cagr, len(period_prices)
    except Exception as e:
        return np.nan, np.nan

def calculate_volatility(returns):
    """計算年化波動率"""
    if isinstance(returns, pd.DataFrame):
        returns = returns.iloc[:, 0]
    return returns.std() * np.sqrt(252)

def calculate_sharpe(cagr, volatility, rf=0.015):
    """計算夏普比率"""
    return (cagr - rf) / volatility if volatility != 0 else np.nan

def calculate_max_drawdown(prices):
    """計算最大回撤"""
    if isinstance(prices, pd.DataFrame):
        prices = prices.iloc[:, 0]
    cummax = prices.cummax()
    drawdown = (prices - cummax) / cummax
    return drawdown.min()

def tracking_error(etf_returns, benchmark_returns):
    """計算追蹤誤差"""
    if isinstance(etf_returns, pd.DataFrame):
        etf_returns = etf_returns.iloc[:, 0]
    if isinstance(benchmark_returns, pd.DataFrame):
        benchmark_returns = benchmark_returns.iloc[:, 0]
    diff = etf_returns - benchmark_returns
    return np.std(diff) * np.sqrt(252)

def calculate_dividend_yield(ticker, start_date, end_date):
    """計算股息殖利率 - 使用TWSE官方資料"""
    try:
        print(f"  🔍 正在獲取 {ticker} 的股息資料...")
        
        # 提取股票代號（移除.TW後綴）
        stock_id = ticker.replace('.TW', '')
        print(f"  📊 查詢股票代號: {stock_id}")
        
        # 使用TWSE官方資料（台股ETF）
        try:
            twse_dividend_df = pd.DataFrame()  # 使用本地字典代替爬蟲
            
            if not twse_dividend_df.empty:
                print(f"  ✅ 從TWSE獲取到 {len(twse_dividend_df)} 筆配息記錄")
                
                # 轉換日期格式
                from datetime import datetime
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                
                # 篩選期間內的配息（擴大到過去1年）
                search_start = start_dt.replace(year=start_dt.year - 1)
                
                # 確保除息交易日欄位存在且為datetime
                if '除息交易日' in twse_dividend_df.columns:
                    twse_dividend_df = twse_dividend_df.dropna(subset=['除息交易日'])
                    period_dividends = twse_dividend_df[
                        (twse_dividend_df['除息交易日'] >= search_start) & 
                        (twse_dividend_df['除息交易日'] <= end_dt)
                    ]
                    
                    if not period_dividends.empty:
                        # 計算總配息（假設配息欄位為'現金股利'）
                        if '現金股利' in period_dividends.columns:
                            total_dividend = period_dividends['現金股利'].sum()
                            print(f"  💰 {ticker} 期間總配息: {total_dividend:.4f}")
                            
                            # 獲取最新價格
                            try:
                                df = download_price_data(ticker, start_date, end_date)
                                if not df.empty:
                                    current_price = float(df['Close'].iloc[-1])
                                    if current_price and current_price > 0:
                                        yield_rate = (total_dividend / current_price) * 100
                                        print(f"  🎯 {ticker} 股息殖利率: {yield_rate:.2f}%")
                                        return round(yield_rate, 2)
                                else:
                                    print(f"  ❌ {ticker} 無法獲取價格資料")
                                    return None
                            except Exception as price_error:
                                print(f"  ❌ {ticker} 獲取價格失敗: {price_error}")
                                return None
                        else:
                            print(f"  ⚠️  {ticker} TWSE資料中找不到現金股利欄位")
                    else:
                        print(f"  📅 {ticker} 在查詢期間內無配息記錄")
                else:
                    print(f"  ⚠️  {ticker} TWSE資料中找不到除息交易日欄位")
            else:
                print(f"  📭 {ticker} TWSE無配息資料")
                return None
        
        except Exception as twse_error:
            print(f"  ❌ TWSE查詢失敗: {twse_error}")
            return None
        
    except Exception as e:
        print(f"  ❌ {ticker} 股息殖利率計算失敗: {e}")
        return None

def get_dividend_yield(ticker):
    """從字典獲取股息殖利率"""
    return dividend_yield_dict.get(ticker, 'N/A')

# 暫時手動設定股息殖利率字典（基於最新公開資料）
dividend_yield_dict = {
    # 主動型 ETF（成立較新，股息記錄較少）
    '00980A.TW': 2.0,   # 野村台灣優選
    '00981A.TW': 1.5,   # 統一台股增長
    '00982A.TW': 2.0,   # 群益台灣強棒
    '00983A.TW': 0.8,   # 中信ARK創新（科技股為主，殖利率較低）
    '00984A.TW': 4.0,   # 安聯台灣高息（專注高股息）
    '00985A.TW': 2.0,   # 野村台灣50
    '00980D.TW': 3.5,   # 聯博投等入息（債券型，較高殖利率）
    
    # 被動型 ETF（成立較久，有實際股息記錄）
    '0050.TW': 2.8,     # 台灣50
    '006208.TW': 2.9,   # 富邦台50
    '0056.TW': 5.5,     # 元大高股息
    '00878.TW': 4.2,     # 國泰永續高股息
    # 美股被動型 ETF
    '00646.TW': 1.5,  # S&P500，成長導向，股息較低
    '00662.TW': 0.7,  # NASDAQ，科技股為主，股息很低
    '00757.TW': 0.4   # FANG+，成長股，股息極低
}

# 從配置中獲取換手率（如果配置中有 turnover_ratio 字段）
turnover_dict = config.get('turnover_ratio', {})


def calculate_alpha_beta(etf_returns, benchmark_returns, rf_rate):
    """計算Alpha和Beta
    
    Alpha = ETF年化報酬率 - (無風險利率 + Beta × (基準年化報酬率 - 無風險利率))
    Beta = ETF報酬與基準報酬的協變數 / 基準報酬的方差
    """
    try:
        # 確保長度相同，使用交集index
        common_idx = etf_returns.index.intersection(benchmark_returns.index)
        
        if len(common_idx) < 2:
            return np.nan, np.nan
        
        etf_ret = etf_returns.loc[common_idx]
        bench_ret = benchmark_returns.loc[common_idx]
        
        # 計算Beta
        covariance = np.cov(etf_ret, bench_ret)[0, 1]
        bench_variance = np.var(bench_ret)
        
        if bench_variance == 0:
            return np.nan, np.nan
        
        beta = covariance / bench_variance
        
        # 計算年化報酬率
        periods_per_year = 252  # 交易日
        total_periods = len(etf_ret)
        years = total_periods / periods_per_year
        
        if years <= 0:
            return np.nan, np.nan
        
        etf_annual_return = (((1 + etf_ret).prod()) ** (1 / years) - 1)
        bench_annual_return = (((1 + bench_ret).prod()) ** (1 / years) - 1)
        
        # 計算Alpha
        alpha = etf_annual_return - (rf_rate + beta * (bench_annual_return - rf_rate))
        
        return alpha * 100, beta  # Alpha 轉換為百分比
        
    except (ValueError, ZeroDivisionError):
        return np.nan, np.nan


def get_etf_data(ticker, common_start_date, end_date, benchmark_returns, risk_free_rate, annualize=True):
    """獲取ETF數據並計算指標
    
    Args:
        ticker: ETF 代碼
        common_start_date: 起始日期
        end_date: 結束日期
        benchmark_returns: 基準報酬率序列
        risk_free_rate: 無風險利率
        annualize: 是否年化報酬率（True=年化，False=實績）
    """
    try:
        print(f"開始分析 {ticker}...")
        
        # 清理ticker格式
        clean_ticker = ticker.strip()
        print(f"  清理後的ticker: '{clean_ticker}'")
        
        # 下載完整歷史資料（用於計算 1 年和 3 年報酬率）
        df_full = download_price_data(clean_ticker, start_date='2015-01-01', end_date=end_date)
        
        # 下載統一期間資料（用於計算全期報酬和其他指標）
        df = download_price_data(clean_ticker, start_date=common_start_date, end_date=end_date)
        
        if df.empty:
            print(f"{clean_ticker} 無資料")
            return None
        
        df.dropna(inplace=True)
        
        if len(df) < 10:
            print(f"{clean_ticker} 有效資料太少")
            return None
        
        # 用完整歷史資料計算 1 年和 3 年報酬率
        if not df_full.empty:
            prices_full = df_full['Close']
            if isinstance(prices_full, pd.DataFrame):
                prices_full = prices_full.iloc[:, 0]
            
            # 1 年報酬率
            if len(prices_full) >= 252:
                period_1y_prices = prices_full.iloc[-252:]
                start_1y = float(period_1y_prices.iloc[0])
                end_1y = float(period_1y_prices.iloc[-1])
                years_1y = len(period_1y_prices) / 252
                ret_1y = (end_1y / start_1y) ** (1 / years_1y) - 1
                days_1y = len(period_1y_prices)
            else:
                ret_1y = np.nan
                days_1y = len(prices_full)
            
            # 3 年報酬率
            if len(prices_full) >= 756:
                period_3y_prices = prices_full.iloc[-756:]
                start_3y = float(period_3y_prices.iloc[0])
                end_3y = float(period_3y_prices.iloc[-1])
                years_3y = len(period_3y_prices) / 252
                ret_3y = (end_3y / start_3y) ** (1 / years_3y) - 1
                days_3y = len(period_3y_prices)
            else:
                ret_3y = np.nan
                days_3y = len(prices_full)
            
            if not (pd.isna(ret_1y) and pd.isna(ret_3y)):
                ret_1y_pct = f"{ret_1y*100:.2f}%" if not pd.isna(ret_1y) else "N/A"
                ret_3y_pct = f"{ret_3y*100:.2f}%" if not pd.isna(ret_3y) else "N/A"
                print(f"  📊 完整歷史：{len(df_full)} 天 | 1年: {ret_1y_pct} | 3年: {ret_3y_pct}")
        else:
            ret_1y, ret_3y = np.nan, np.nan
            print(f"  ⚠️  {clean_ticker} 無完整歷史資料")
            
        # 提取價格和收益率（統一期間）
        prices = df['Close']
        if isinstance(prices, pd.DataFrame):
            prices = prices.iloc[:, 0]
        returns = prices.pct_change().dropna()

        # 計算各項指標（根據 annualize 參數決定是否年化）
        cagr, data_years = calculate_returns(prices, annualize=annualize)
        
        # 檢測可能的股票分割或其他異常（年化報酬率 < -50% 通常表示有問題）
        if annualize and data_years >= 1.0 and cagr is not None and cagr < -0.5:
            # 檢查起始和結束股價，看是否存在大幅下跌
            start_price = float(prices.iloc[0])
            end_price = float(prices.iloc[-1])
            total_return = (end_price / start_price) - 1
            
            if total_return > -0.3:  # 實際總報酬不是那麼差，可能是分割問題
                print(f"  ⚠️  {clean_ticker} 可能存在股票分割或復權問題（年化: {cagr*100:.2f}%, 實績: {total_return*100:.2f}%）")
                print(f"      建議檢查：{start_price:.2f} → {end_price:.2f}")
        
        vol = calculate_volatility(returns)
        sharpe = calculate_sharpe(cagr, vol, rf=risk_free_rate)
        mdd = calculate_max_drawdown(prices)
        
        # 計算追蹤誤差
        try:
            if benchmark_returns is not None and len(benchmark_returns) > 0:
                common_idx = returns.index.intersection(benchmark_returns.index)
                if len(common_idx) > 10:
                    te = tracking_error(returns.loc[common_idx], benchmark_returns.loc[common_idx])
                else:
                    te = np.nan
            else:
                te = np.nan
        except:
            te = np.nan
        
        # 股息殖利率計算：優先使用TWSE官方資料，失敗則用字典備案
        print(f"📈 正在計算 {clean_ticker} 的股息殖利率...")
        dividend_yield = calculate_dividend_yield(clean_ticker, common_start_date, end_date)
        
        if dividend_yield is None:
            print(f"  🔄 {clean_ticker} 所有計算方法都失敗，使用預設字典值")
            dividend_yield = dividend_yield_dict.get(clean_ticker, 'N/A')
            if dividend_yield != 'N/A':
                print(f"  ✅ {clean_ticker} 使用字典預設股息殖利率: {dividend_yield}%")
            else:
                print(f"  ⚠️  {clean_ticker} 字典中也無數據，設為 N/A")
        else:
            print(f"  🎯 {clean_ticker} 成功計算股息殖利率: {dividend_yield}%")

        # 獲取其他資料
        turnover = turnover_dict.get(clean_ticker, 'N/A')
        expense = expense_ratio_dict.get(clean_ticker, 'N/A')
        
        print(f"  📊 {clean_ticker} 換手率: {turnover}%")
        print(f"  💰 {clean_ticker} 管理費: {expense}%")

        print(f"{clean_ticker} 分析完成 - 期間: {data_years:.2f}年, CAGR: {cagr:.2%}")
        
        # 計算 Alpha 和 Beta
        alpha, beta = np.nan, np.nan
        if benchmark_returns is not None and len(benchmark_returns) > 0:
            # 只有當 ETF 有足夠的數據點時才計算 Alpha/Beta
            # 最少需要 5 個交易日，這樣才有足夠的變異來計算相關係數
            if len(returns) >= 5:
                alpha, beta = calculate_alpha_beta(returns, benchmark_returns, risk_free_rate)
                print(f"  ✅ {clean_ticker} Alpha/Beta 計算完成")
            else:
                print(f"⚠️  {clean_ticker} 數據點不足 ({len(returns)} 天)，跳過 Alpha/Beta 計算")
        
        # 從 etf_list 中查找 ETF 名稱（支持對象和數組格式）
        etf_name = '未知'
        for item in etf_list:
            if isinstance(item, dict):
                if item.get('ticker', '').strip() == ticker:
                    etf_name = item.get('name', '未知').strip()
                    break
            else:
                if len(item) > 0 and item[0].strip() == ticker:
                    etf_name = item[1].strip() if len(item) > 1 else '未知'
                    break
        
        return {
            '證券代碼': clean_ticker,
            '名稱': etf_name,
            '數據天數': len(df),  # 統一期間的資料天數
            '完整歷史天數': len(df_full) if not df_full.empty else 0,  # 完整歷史資料天數
            '資料期間 (年)': round(data_years, 2),
            '1年年化報酬率 (%)': round(ret_1y*100, 2) if not pd.isna(ret_1y) else 'N/A',
            '3年年化報酬率 (%)': round(ret_3y*100, 2) if not pd.isna(ret_3y) else 'N/A',  # 3年年化報酬率
            'Alpha': round(alpha, 2) if not pd.isna(alpha) else 'N/A',
            'Beta': round(beta, 2) if not pd.isna(beta) else 'N/A',
            '夏普比率': round(sharpe, 2) if not pd.isna(sharpe) else 'N/A',
            '年化波動率 (%)': round(vol*100, 2) if not pd.isna(vol) else 'N/A',
            '最大回撤 (%)': round(mdd*100, 2) if not pd.isna(mdd) else 'N/A',
            '追蹤誤差 (%)': round(te*100, 2) if not pd.isna(te) else 'N/A',
            '換手率 (%)': turnover,
            '管理費 (%)': expense,
            '股息殖利率 (%)': dividend_yield
        }
    except Exception as e:
        print(f"{ticker} 分析失敗: {e}")
        return None
    
# 修正 matplotlib 後端設定，避免 tkinter 衝突
def setup_matplotlib_backend():
    """設定 matplotlib 後端，避免 tkinter 衝突"""
    import matplotlib
    
    # 設定非互動式後端
    matplotlib.use('Agg')  # 使用 Anti-Grain Geometry backend
    
    import matplotlib.pyplot as plt
    
    # 確保不會開啟 GUI 視窗
    plt.ioff()  # 關閉互動模式
    
    return plt


def add_timestamp_to_figure(fig, timestamp=None):
    """在圖表底部添加生成時間戳"""
    if timestamp is None:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 在圖表底部添加時間戳文本
    fig.text(0.99, 0.01, f'Generated: {timestamp}', 
             ha='right', va='bottom', fontsize=8, style='italic', alpha=0.6)


def save_figure_with_timestamp(fig, output_path, dpi=300, bbox_inches='tight'):
    """保存圖表並自動添加時間戳"""
    add_timestamp_to_figure(fig)
    fig.savefig(output_path, dpi=dpi, bbox_inches=bbox_inches)


def setup_chinese_font():
    """設定中文字體（已通過 font_config 改進版本）"""
    # 字體配置已在導入時完成
    pass


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

def plot_radar_chart(df_results, etf_type_prefix=""):
    """繪製多指標雷達圖（分類拆分，使用不同標記）
    
    Args:
        df_results: ETF 分析結果 DataFrame
        etf_type_prefix: ETF 類型前綴（如 "Active_", "HighDividend_", "Industry_"）
    """
    from math import pi
    import os
    
    plt = setup_matplotlib_backend()
    setup_chinese_font()
    
    categories = ['年化報酬率', '夏普比率', '波動率(反)', '最大回撤(反)', '追蹤誤差(反)']
    categories_en = ['Return', 'Sharpe', 'Low Volatility', 'Low Max DD', 'Low Tracking Error']
    
    N = len(categories)
    angles = [n / float(N) * 2 * pi for n in range(N)]
    angles += angles[:1]
    
    # 分類ETF資料（從 JSON 配置讀取）
    us_etfs = []
    tw_stock_etfs = []
    tw_dividend_etfs = []
    
    for _, row in df_results.iterrows():
        ticker = row['證券代碼'].strip()
        name = row['名稱'].strip()
        etf_type = config.get('etf_type', {}).get(ticker)
        
        if etf_type == 'us':
            us_etfs.append(row)
        elif etf_type == 'dividend':
            tw_dividend_etfs.append(row)
        else:
            # 預設為 taiwan_stock
            tw_stock_etfs.append(row)
    
    # 收集數據範圍（基於全部資料）
    all_returns, all_sharpe, all_vol, all_dd, all_te = [], [], [], [], []
    
    for _, row in df_results.iterrows():
        if row.get('3年年化報酬率 (%)', row.get('績效 (%)', 'N/A')) != 'N/A':
            all_returns.append(float(row.get('3年年化報酬率 (%)', row.get('績效 (%)', 'N/A'))))
        if row['夏普比率'] != 'N/A':
            all_sharpe.append(float(row['夏普比率']))
        if row['年化波動率 (%)'] != 'N/A':
            all_vol.append(float(row['年化波動率 (%)']))
        if row['最大回撤 (%)'] != 'N/A':
            # 最大回撤取絕對值後再加入範圍計算
            all_dd.append(abs(float(row['最大回撤 (%)'])))
        if row['追蹤誤差 (%)'] != 'N/A':
            all_te.append(float(row['追蹤誤差 (%)']))
    
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
            
            # 使用 smart_label_with_ticker 處理名稱
            display_name = smart_label_with_ticker(name, ticker).replace('\n', ' ')
            
            # 計算標準化數值
            values = []
            ret_val = float(row.get('3年年化報酬率 (%)', row.get('績效 (%)', 'N/A'))) if row.get('3年年化報酬率 (%)', row.get('績效 (%)', 'N/A')) != 'N/A' else return_min
            values.append(normalize_value(ret_val, return_min, return_max, reverse=False))
            
            sharpe_val = float(row['夏普比率']) if row['夏普比率'] != 'N/A' else sharpe_min
            values.append(normalize_value(sharpe_val, sharpe_min, sharpe_max, reverse=False))
            
            vol_val = float(row['年化波動率 (%)']) if row['年化波動率 (%)'] != 'N/A' else vol_max
            values.append(normalize_value(vol_val, vol_min, vol_max, reverse=True))
            
            # 最大回撤取絕對值（在all_dd收集時已轉為正數，這裡直接使用）
            dd_val = float(row['最大回撤 (%)']) if row['最大回撤 (%)'] != 'N/A' else dd_min
            if dd_val < 0:
                dd_val = abs(dd_val)
            values.append(normalize_value(dd_val, dd_min, dd_max, reverse=True))
            
            te_val = float(row['追蹤誤差 (%)']) if row['追蹤誤差 (%)'] != 'N/A' else te_max
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
        
        ax.set_title(title, fontsize=18, pad=40, fontweight='bold')
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
        
        # 使用 smart_label_with_ticker 處理名稱（總覽圖用更簡潔版本）
        display_name = smart_label_with_ticker(name, ticker).replace('\n', ' ')
        
        # 計算標準化數值
        values = []
        ret_val = float(row.get('3年年化報酬率 (%)', row.get('績效 (%)', 'N/A'))) if row.get('3年年化報酬率 (%)', row.get('績效 (%)', 'N/A')) != 'N/A' else return_min
        values.append(normalize_value(ret_val, return_min, return_max, reverse=False))
        
        sharpe_val = float(row['夏普比率']) if row['夏普比率'] != 'N/A' else sharpe_min
        values.append(normalize_value(sharpe_val, sharpe_min, sharpe_max, reverse=False))
        
        vol_val = float(row['年化波動率 (%)']) if row['年化波動率 (%)'] != 'N/A' else vol_max
        values.append(normalize_value(vol_val, vol_min, vol_max, reverse=True))
        
        # 最大回撤取絕對值（在all_dd收集時已轉為正數，這裡直接使用）
        dd_val = float(row['最大回撤 (%)']) if row['最大回撤 (%)'] != 'N/A' else dd_min
        if dd_val < 0:
            dd_val = abs(dd_val)
        values.append(normalize_value(dd_val, dd_min, dd_max, reverse=True))
        
        te_val = float(row['追蹤誤差 (%)']) if row['追蹤誤差 (%)'] != 'N/A' else te_max
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
    
    ax.set_title(title, fontsize=18, pad=40, fontweight='bold')
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
    
    # 計算冠軍
    metrics_data = {
        '年化報酬率': ([], '3年年化報酬率 (%)'),
        '夏普比率': ([], '夏普比率'),
        '低波動': ([], '年化波動率 (%)'),
        '低回撤': ([], '最大回撤 (%)'),
        '低追蹤誤差': ([], '追蹤誤差 (%)'),
    }
    
    for _, row in df_results.iterrows():
        try:
            metrics_data['年化報酬率'][0].append((float(row.get('3年年化報酬率 (%)', row.get('績效 (%)', 'N/A'))), row['名稱'].strip(), row['證券代碼'].strip()))
            metrics_data['夏普比率'][0].append((float(row['夏普比率']), row['名稱'].strip(), row['證券代碼'].strip()))
            metrics_data['低波動'][0].append((float(row['年化波動率 (%)']), row['名稱'].strip(), row['證券代碼'].strip()))
            metrics_data['低回撤'][0].append((float(row['最大回撤 (%)']), row['名稱'].strip(), row['證券代碼'].strip()))
            metrics_data['低追蹤誤差'][0].append((float(row['追蹤誤差 (%)']), row['名稱'].strip(), row['證券代碼'].strip()))
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

def plot_price_trend(etf_list, config, common_start_date, latest_date, etf_type_prefix=""):
    """繪製淨值成長折線圖（總圖+分類子圖，以基準指數正規化）
    
    Args:
        etf_list: ETF 列表
        config: ETF 配置
        common_start_date: 統一的起始日期
        latest_date: 結束日期
        etf_type_prefix: ETF 類型前綴（如 "Active_", "HighDividend_", "Industry_"）
    """
    plt = setup_matplotlib_backend()
    setup_chinese_font()
    
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
        try:
            # 台股基準 - 改用台灣50(0050)以保持與trend_tw_stock.png一致
            print("正在下載台灣50基準指數...")
            tw_index = download_price_data('0050.TW', start_date=start_date_3y, end_date=latest_date)
            if not tw_index.empty:
                tw_prices = tw_index['Close']
                if isinstance(tw_prices, pd.DataFrame):
                    tw_prices = tw_prices.iloc[:, 0]
                tw_normalized = (tw_prices / tw_prices.iloc[0]) * 100
                plt.plot(tw_normalized.index, tw_normalized, 
                        label='台灣50 (0050)', linewidth=3, color='#FF0000', 
                        linestyle='--', alpha=0.8)
        except Exception as e:
            print(f"台灣50下載失敗: {e}")
        
        try:
            # 美股基準 - S&P 500
            print("正在下載美股基準指數...")
            sp500_index = download_price_data('^GSPC', start_date=start_date_3y, end_date=latest_date)
            if not sp500_index.empty:
                sp500_prices = sp500_index['Close']
                if isinstance(sp500_prices, pd.DataFrame):
                    sp500_prices = sp500_prices.iloc[:, 0]
                sp500_normalized = (sp500_prices / sp500_prices.iloc[0]) * 100
                plt.plot(sp500_normalized.index, sp500_normalized, 
                        label='S&P 500指數', linewidth=3, color='#0000FF', 
                        linestyle='-.', alpha=0.8)
        except Exception as e:
            print(f"S&P 500指數下載失敗: {e}")
        
        # 繪製各ETF（較細的線條）
        for i, (ticker, name) in enumerate(etf_info.items()):
            try:
                df = download_price_data(ticker.strip(), start_date=start_date_3y, end_date=latest_date)
                if not df.empty:
                    prices = df['Close']
                    if isinstance(prices, pd.DataFrame):
                        prices = prices.iloc[:, 0]
                    
                    # 正規化為起始點100
                    normalized_prices = (prices / prices.iloc[0]) * 100
                    
                    color = colors[i % len(colors)]
                    line_style = '-'
                    alpha = 0.7
                    
                    # 使用 smart_label_with_ticker 命名
                    display_name = smart_label_with_ticker(name.strip(), ticker.strip()).replace('\n', ' ')
                    
                    plt.plot(normalized_prices.index, normalized_prices, 
                            label=display_name, linewidth=2, color=color, 
                            linestyle=line_style, alpha=alpha)
            except Exception as e:
                print(f"{ticker} 折線圖繪製失敗: {e}")
        
        # 設定標題和標籤
        try:
            plt.title('ETF vs 基準指數總覽 (基準點=100)\n紅線：台股加權 | 藍線：S&P500', 
                     fontsize=16, fontweight='bold')
            plt.xlabel('日期', fontsize=12)
            plt.ylabel('相對淨值 (起始=100)', fontsize=12)
        except:
            plt.title('ETF vs Benchmark Overview (Base=100)\nRed: Taiwan Index | Blue: S&P500', 
                     fontsize=16, fontweight='bold')
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
        
        # 找出該組ETF的最晚上市日期
        latest_etf_start = None
        etf_start_dates = {}
        
        print(f"\n🔍 檢查{category_name}ETF上市日期...")
        for ticker in etf_group.keys():
            try:
                # 從很早的日期開始搜尋，找出實際上市日
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
        
        # 繪製該組ETF，使用絕對正規化（各自從100開始）
        colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#C70039', '#7BC225']
        
        for i, (ticker, name) in enumerate(etf_group.items()):
            try:
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
                    
                    # 使用 smart_label_with_ticker 命名
                    display_name = smart_label_with_ticker(name, ticker).replace('\n', ' ')
                    
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
            
            plt.title(title, fontsize=14, fontweight='bold')
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
    print("📈 開始繪製趨勢圖...")
    
    # 判斷是否為主動式 ETF（使用固定起始日期）
    use_fixed_start_for_trends = (config_type == 'active_etf')
    fixed_start_date_for_trends = start_date_3y if use_fixed_start_for_trends else None
    
    # 總覽圖
    plot_overview()
    
    # 美股相關ETF vs S&P500
    plot_category_trend(
        us_etfs, 
        '^GSPC', 
        'S&P500', 
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


def plot_multi_metrics_comparison(df_results, etf_type_prefix="", annualize=True):
    """繪製多指標柱狀圖：績效/年化報酬率、Alpha、Beta、夏普比率、MDD、標準差、費用率、追蹤誤差"""
    plt = setup_matplotlib_backend()
    setup_chinese_font()

    print("\n📊 繪製多指標比較柱狀圖...")
    
    # 決定績效列的名稱
    if annualize:
        return_col = '3年年化報酬率 (%)'
        return_label = '3年年化報酬率 (%)'
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
    sort_col = '3年年化報酬率 (%)' if annualize else '績效 (%)'
    
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
        print(f"\n✅ 多指標圖表已儲存: {output_path}")
    except Exception as e:
        print(f"❌ 保存多指標圖表失敗: {e}")
    
    plt.close()


def plot_dual_column_performance(df_results, etf_type_prefix=""):
    """繪製雙柱狀圖表：1年年化報酬率 vs 3年年化報酬率（業界標準）"""
    plt = setup_matplotlib_backend()
    setup_chinese_font()
    
    print("\n📊 繪製雙柱狀績效圖表（1年 vs 3年）...")
    
    try:
        fig, ax = plt.subplots(figsize=(16, 9))
        
        # 準備數據
        names = []
        ret_1y_list = []
        ret_3y_list = []
        
        for _, row in df_results.iterrows():
            ticker = row['證券代碼'].strip()
            name = row['名稱'].strip()
            
            # 1 年報酬率
            ret_1y = row.get('1年年化報酬率 (%)', 'N/A')
            ret_1y = float(ret_1y) if ret_1y != 'N/A' else None
            
            # 3 年報酬率（用年化報酬率欄位）
            ret_3y = row.get('3年年化報酬率 (%)', 'N/A')
            ret_3y = float(ret_3y) if ret_3y != 'N/A' else None
            
            names.append(f"{ticker}\n{name}")
            ret_1y_list.append(ret_1y if ret_1y is not None else 0)
            ret_3y_list.append(ret_3y if ret_3y is not None else 0)
        
        # 設定 X 軸位置
        x = np.arange(len(names))
        width = 0.35
        
        # 繪製雙柱
        bars1 = ax.bar(x - width/2, ret_1y_list, width, label='1年年化報酬率', color='#3498db', alpha=0.8, edgecolor='black', linewidth=1)
        bars2 = ax.bar(x + width/2, ret_3y_list, width, label='3年年化報酬率', color='#e74c3c', alpha=0.8, edgecolor='black', linewidth=1)
        
        # 添加數值標籤
        for bar in bars1:
            height = bar.get_height()
            if height != 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        for bar in bars2:
            height = bar.get_height()
            if height != 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        # 設定標籤
        ax.set_xlabel('ETF', fontsize=FONT_SIZE_CONFIG['label_large'], fontweight='bold')
        ax.set_ylabel('3年年化報酬率 (%)', fontsize=FONT_SIZE_CONFIG['label_large'], fontweight='bold')
        ax.set_title('ETF 績效對比：1年 vs 3年年化報酬率\n（紅色虛線表示無 3 年數據，顯示全部 ETF）', 
                    fontsize=FONT_SIZE_CONFIG['title_large'], fontweight='bold', pad=20)
        ax.set_xticks(x)
        ax.set_xticklabels(names, fontsize=FONT_SIZE_CONFIG['tick_small'], rotation=45, ha='right')
        
        # 添加基準線
        ax.axhline(y=0, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
        ax.grid(True, alpha=0.3, axis='y')
        
        # 圖例
        ax.legend(fontsize=FONT_SIZE_CONFIG['label_medium'], loc='upper right', frameon=True, fancybox=True, shadow=True)
        
        plt.tight_layout()
        
        # 保存
        output_path = os.path.join(output_folder, f'{etf_type_prefix}etf_dual_column_performance.png')
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"  ✅ 雙柱狀圖表已儲存: {output_path}")
        
    except Exception as e:
        print(f"  ❌ 雙柱狀圖表生成失敗: {e}")
    
    plt.close()


def plot_performance_comparison(df_results, etf_type_prefix="", annualize=True):
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
        ret = float(row.get('3年年化報酬率 (%)', row.get('績效 (%)', 'N/A')))
        
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
        
        # 美股基準（也使用相同時間範圍和計算方式）
        if us_etfs:
            voo = download_price_data('VOO', start_date=bench_start_date, end_date=latest_date)
            sp500 = download_price_data('^GSPC', start_date=bench_start_date, end_date=latest_date)
            
            if isinstance(voo, pd.DataFrame) and not voo.empty:
                years_voo = len(voo['Close']) / 252
                total_ret_voo = ((voo['Close'].iloc[-1] / voo['Close'].iloc[0]) - 1) * 100
                
                if bench_annualize and years_voo >= 1.0:
                    ret_voo = float(((1 + total_ret_voo/100) ** (1 / years_voo) - 1) * 100) if years_voo > 0 else total_ret_voo
                else:
                    ret_voo = float(total_ret_voo)
                benchmark_data['VOO'] = ('VOO S&P500', ret_voo)
            elif isinstance(sp500, pd.DataFrame) and not sp500.empty:
                years_sp500 = len(sp500['Close']) / 252
                total_ret_sp500 = ((sp500['Close'].iloc[-1] / sp500['Close'].iloc[0]) - 1) * 100
                
                if bench_annualize and years_sp500 >= 1.0:
                    ret_sp500 = float(((1 + total_ret_sp500/100) ** (1 / years_sp500) - 1) * 100) if years_sp500 > 0 else total_ret_sp500
                else:
                    ret_sp500 = float(total_ret_sp500)
                benchmark_data['SP500'] = ('^GSPC S&P500', ret_sp500)
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
        print(f"\n  📊 生成台股 ETF 柱狀圖 (_TW)...")
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
        
        ax.set_title('台股 ETF 年化報酬率比較 (含基準)', fontsize=FONT_SIZE_CONFIG['title_large'], fontweight='bold')
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
        timestamp_title = f'台股 ETF 年化報酬率比較 (含基準) {current_time}生成'
        ax.set_title(timestamp_title, fontsize=FONT_SIZE_CONFIG['title_large'], fontweight='bold')
        
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
        
        ax.set_title('美股 ETF 年化報酬率比較 (含基準)', fontsize=FONT_SIZE_CONFIG['title_large'], fontweight='bold')
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


if __name__ == '__main__':
    print(f"\n🚀 開始執行 {config_type} 配置...")
    
    # 首先設定 matplotlib 後端
    print("  📊 設定 matplotlib 後端...")
    plt = setup_matplotlib_backend()

    # 1. 找出統一的比較期間
    print("  📅 查找統一比較期間...")
    # 主動式 ETF 使用固定的 7/22 起始日期，其他配置使用最晚上市日期
    use_fixed_start = (config_type == 'active_etf')
    common_start_date = find_common_start_date(etf_list, start_date_3y, latest_date, use_fixed_start=use_fixed_start)
    
    # 2. 下載0050作為基準（用於計算追蹤誤差）
    print(f"\n下載基準指數 0050...")
    benchmark_returns = None
    sp500_returns = None
    try:
        # 台股基準
        benchmark_df = download_price_data('0050.TW', start_date=common_start_date, end_date=latest_date)
        if not benchmark_df.empty:
            benchmark_prices = benchmark_df['Close']
            if isinstance(benchmark_prices, pd.DataFrame):
                benchmark_prices = benchmark_prices.iloc[:, 0]
            benchmark_returns = benchmark_prices.pct_change().dropna()
            print(f"✅ 基準資料期間: {len(benchmark_returns)} 個交易日")
        else:
            print(f"⚠️  0050 無資料，Alpha/Beta 將無法計算")
            benchmark_returns = None
        
        # 美股基準 - S&P 500（用於視覺化比較）
        sp500_df = download_price_data('^GSPC', start_date=common_start_date, end_date=latest_date)
        if not sp500_df.empty:
            sp500_prices = sp500_df['Close']
            if isinstance(sp500_prices, pd.DataFrame):
                sp500_prices = sp500_prices.iloc[:, 0]
            sp500_returns = sp500_prices.pct_change().dropna()
            print(f"✅ 美股基準資料期間: {len(sp500_returns)} 個交易日")
        else:
            print(f"⚠️  S&P500 無資料")
            sp500_returns = None
    except Exception as e:
        print(f"⚠️  基準指數下載異常: {e}，Alpha/Beta 將無法計算")
        benchmark_returns = None
        sp500_returns = None
    
    # 3. 分析所有ETF
    print(f"\n開始分析各ETF（統一期間: {common_start_date} 至 {latest_date}）...")
    results = []
    
    # 對於 active_etf，不進行年化；其他類型進行年化
    should_annualize = (config_type != 'active_etf')
    
    for item in etf_list:
        # 支持對象和數組格式
        if isinstance(item, dict):
            ticker = item.get('ticker', '').strip()
        else:
            ticker = item[0].strip()
        
        if not ticker:
            continue
        # 忽略可選的第3個元素（分類信息）
        data = get_etf_data(ticker, common_start_date, latest_date, benchmark_returns, risk_free_rate, annualize=should_annualize)
        if data:
            results.append(data)
    
    # 4. 顯示結果
    if results:
        df_results = pd.DataFrame(results)
        
        # 不過濾 ETF - 全部顯示，1 年柱狀全部有，3 年柱狀只有成立滿 3 年的才有
        print(f"\n📊 分析完成")
        min_days_3years = 756  # 3 年 = 756 個交易日
        etf_3y_count = len(df_results[df_results['完整歷史天數'] >= min_days_3years])
        print(f"✅ 共分析 {len(df_results)} 支 ETF（其中 {etf_3y_count} 支滿足 3 年條件）")
        etf_filter_status = f"（共 {len(df_results)} 支，其中 {etf_3y_count} 支有 3 年數據）"
        
        # 按績效/年化報酬率排序
        sort_column = '3年年化報酬率 (%)' if should_annualize else '績效 (%)'
        if sort_column in df_results.columns:
            df_results = df_results.sort_values(sort_column, ascending=False)
        
        print(f"\n{'='*180}")
        print(f"ETF 比較分析結果（統一期間: {common_start_date} 至 {latest_date}）{etf_filter_status}")
        print(f"{'='*180}")

        # 修正後的表格標題 - 單行不換行
        print(f"{'證券代碼':<12} {'名稱':<20} {'期間(年)':<8} {'1年年化(%)':<12} {'3年年化(%)':<12} {'夏普比率':<9} {'波動率(%)':<9} {'最大回撤(%)':<11} {'追蹤誤差(%)':<11}")
        print('-' * 180)

        for _, row in df_results.iterrows():
            # 處理 N/A 和 nan 值的顯示
            def format_value(val, decimal_places=2):
                if val == 'N/A' or pd.isna(val):
                    return 'N/A'
                try:
                    if isinstance(val, (int, float)):
                        return f"{val:.{decimal_places}f}"
                    return str(val)
                except:
                    return 'N/A'
            
            # 格式化各欄位
            ticker = row['證券代碼']
            name = row['名稱'][:18] + '..' if len(row['名稱']) > 20 else row['名稱']
            period = format_value(row['資料期間 (年)'], 2)
            ret_1y = format_value(row.get('1年年化報酬率 (%)', 'N/A'), 2)
            annual_return = format_value(row.get('3年年化報酬率 (%)', row.get('績效 (%)', 'N/A')), 2)
            sharpe = format_value(row['夏普比率'], 2)
            volatility = format_value(row['年化波動率 (%)'], 2)
            max_dd = format_value(row['最大回撤 (%)'], 2)
            tracking_error = format_value(row['追蹤誤差 (%)'], 2)
            
            print(f"{ticker:<12} {name:<20} {period:<8} {ret_1y:<12} {annual_return:<12} {sharpe:<9} {volatility:<9} {max_dd:<11} {tracking_error:<11}")

        print('-' * 180)

        # 儲存結果到輸出資料夾
        csv_path = os.path.join(output_folder, f'{etf_type_prefix}etf_comparison_unified.csv')
        df_results.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"\n結果已儲存至 {csv_path}")
        
        # 顯示統計摘要
        print(f"\n{'='*60}")
        print("統計摘要:")
        print(f"共分析 {len(results)} 支ETF")
        print(f"統一比較期間: {df_results['資料期間 (年)'].iloc[0]:.2f} 年")
        
        # 打印數據天數摘要
        print(f"\n📊 ETF 數據天數統計:")
        print(f"{'代碼':<12} {'名稱':<20} {'數據天數':<10} {'說明':<50}")
        print("-" * 92)
        
        data_days_dict = {}  # 記錄所有 ETF 的數據天數
        for _, row in df_results.iterrows():
            ticker = row['證券代碼']
            name = row['名稱'][:18] if len(row['名稱']) > 18 else row['名稱']
            days = int(row['數據天數'])
            
            # 判斷數據是否充分
            if days < 20:
                status = "❌ 數據嚴重不足，Alpha/Beta 不可靠"
            elif days < 30:
                status = "⚠️  數據不足，Alpha/Beta 可能不可靠"
            elif days < 60:
                status = "△ 數據有限，Alpha/Beta 需謹慎解讀"
            else:
                status = "✅ 數據充分，Alpha/Beta 可信"
            
            print(f"{ticker:<12} {name:<20} {days:<10} {status:<50}")
            data_days_dict[ticker] = days
        
        print(f"\n📋 數據充分度分類 (>= 30 天可計算 Alpha/Beta):")
        sufficient = sum(1 for d in data_days_dict.values() if d >= 30)
        insufficient = len(data_days_dict) - sufficient
        print(f"  ✅ 數據充分: {sufficient} 支")
        print(f"  ⚠️  數據不足: {insufficient} 支")
        
        # 計算數值型欄位的平均值（使用正確的列名）
        return_col = '3年年化報酬率 (%)' if should_annualize else '績效 (%)'
        numeric_returns = [x for x in df_results[return_col] if x != 'N/A']
        numeric_volatility = [x for x in df_results['年化波動率 (%)'] if x != 'N/A']
        
        return_label = '年化報酬率' if should_annualize else '績效'
        if numeric_returns:
            print(f"平均{return_label}: {np.mean(numeric_returns):.2f}%")
        if numeric_volatility:
            print(f"平均波動率: {np.mean(numeric_volatility):.2f}%")
            
        print(f"{'='*60}")

        # 5. 視覺化
        turnover_chart = plot_turnover_bar(df_results)
        print("\nChart.js 條形圖配置（換手率）：")
        print(turnover_chart)
        # plot_price_trend({ticker: name for ticker, name in etf_list})
        # plot_radar_chart(df_results)
        # print("\n折線圖已儲存為 etf_price_trend.png")
        # print("雷達圖已儲存為 etf_radar_chart.png")

        print("\n📊 正在生成視覺化圖表...")
        
        # 修正字體問題的視覺化
        skip_plots = os.getenv('SKIP_PLOTS', '0') == '1'
        
        if not skip_plots:
            print("\n🎨 開始生成圖表...")
            try:
                print("  📈 1. 繪製價格趨勢圖...")
                plot_price_trend(etf_list, config, common_start_date, latest_date, etf_type_prefix)
                print("  ✅ 價格趨勢圖完成")
            except Exception as e:
                print(f"  ❌ 價格趨勢圖失敗: {e}")
            
            try:
                print("  📊 2. 繪製雷達圖...")
                plot_radar_chart(df_results, etf_type_prefix)
                print("  ✅ 雷達圖完成")
            except Exception as e:
                print(f"  ❌ 雷達圖失敗: {e}")
            
            try:
                print("  📊 3. 繪製多指標比較圖...")
                plot_multi_metrics_comparison(df_results, etf_type_prefix, annualize=should_annualize)
                print("  ✅ 多指標比較圖完成")
            except Exception as e:
                print(f"  ❌ 多指標比較圖失敗: {e}")
            
            try:
                print("  📊 4. 繪製雙柱狀績效圖表（1年 vs 3年）...")
                plot_dual_column_performance(df_results, etf_type_prefix)
                print("  ✅ 雙柱狀績效圖表完成")
            except Exception as e:
                print(f"  ❌ 雙柱狀績效圖表失敗: {e}")
            
            try:
                print("  📊 5. 繪製績效比較圖...")
                plot_performance_comparison(df_results, etf_type_prefix, annualize=should_annualize)
                print("  ✅ 績效比較圖完成")
            except Exception as e:
                print(f"  ❌ 績效比較圖失敗: {e}")
        else:
            print("\n⏭️  跳過圖表生成（SKIP_PLOTS=1）")
        
        print("✅ ETF vs 基準比較圖已儲存為 etf_vs_benchmark_trend.png")
        print("✅ 雷達圖已儲存為 etf_radar_chart.png")
        print(f"✅ 多指標圖表已儲存為 {etf_type_prefix}etf_multi_metrics_comparison.png")
        print(f"✅ 績效比較圖已儲存為 {etf_type_prefix}etf_performance_comparison_TW.png 和 {etf_type_prefix}etf_performance_comparison_US.png")
        print(f"✅ 績效比較圖已儲存為 {etf_type_prefix}etf_performance_comparison.png")
        
        # 額外提供雙基準分析摘要
        print(f"\n{'='*60}")
        print("雙基準分析摘要:")
        print("- 台股基準：用於計算追蹤誤差和相對表現")
        print("- 美股基準：用於比較 00983A (ARK創新) 等跨市場ETF")
        print("- 圖表中可清楚看出各ETF與兩市場的關聯性")
        print(f"{'='*60}")
    else:
        print("沒有成功分析的ETF資料")