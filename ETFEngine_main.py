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
from generate_all_charts import generate_performance_chart

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
plt.ioff()  # 關閉互動模式

# 導入改進的字體配置
from font_config import setup_chinese_font_enhanced, update_font_sizes, FONT_SIZE_CONFIG
from config_loader import load_etf_config

# 設置中文字體和字體大小
setup_chinese_font_enhanced()
update_font_sizes()

# 風險無風險報酬率（全域常數）
risk_free_rate = 0.015

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




def find_common_start_date(etf_list, initial_start_date, end_date, config_type='default', use_fixed_start=False):
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
            df = download_price_data(ticker, start_date=initial_start_date, end_date=end_date, config_type=config_type)
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
    """計算股息殖利率 - 暫時回傳 None，使用 JSON 配置"""
    return None

def get_dividend_yield(ticker, dividend_dict):
    """從字典獲取股息殖利率"""
    return dividend_dict.get(ticker, 'N/A')


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


def get_etf_data(ticker, common_start_date, end_date, benchmark_returns, risk_free_rate, 
                 config, config_type='default', annualize=True):
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
        df_full = download_price_data(clean_ticker, start_date='2015-01-01', end_date=end_date, config_type=config_type)
        
        # 下載統一期間資料（用於計算全期報酬和其他指標）
        df = download_price_data(clean_ticker, start_date=common_start_date, end_date=end_date, config_type=config_type)
        
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
        
        # 從配置獲取字典數據
        dividend_yield_dict = config.get('devidend', config.get('dividend', {}))
        turnover_dict = config.get('turnover_ratio', {})
        expense_ratio_dict = config.get('expense_ratio', {})
        
        # 股息殖利率計算：優先使用TWSE官方資料，失敗則用字典備案
        dividend_yield = calculate_dividend_yield(clean_ticker, common_start_date, end_date)
        
        if dividend_yield is None:
            dividend_yield = dividend_yield_dict.get(clean_ticker, 'N/A')
        
        # 獲取其他資料
        turnover = turnover_dict.get(clean_ticker, 'N/A')
        expense = expense_ratio_dict.get(clean_ticker, 'N/A')

        cagr_pct = cagr * 100 if not pd.isna(cagr) else 0
        print(f"{clean_ticker} 分析完成 - 期間: {data_years:.2f}年, CAGR: {cagr_pct:.2f}%")
        
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
            '1年年化報酬率 (%)': round(ret_1y*100, 2) if not pd.isna(ret_1y) else 9999,
            '3年年化報酬率 (%)': round(ret_3y*100, 2) if not pd.isna(ret_3y) else 9999,  # 3年年化報酬率
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



if __name__ == '__main__':
    import sys
    
    # Get config type from command line argument
    if len(sys.argv) > 1:
        config_type = sys.argv[1]
    else:
        config_type = 'industry_etf'  # default
    
    print(f"📋 使用配置: {config_type}")
    
    # Load ETF list based on config_type
    config = load_etf_config(config_type)
    etf_list = config['etf_list']
    expense_ratio_dict = config['expense_ratio']
    
    # Set file prefix based on config type
    if config_type == 'active_etf':
        etf_type_prefix = 'Active_'
    elif config_type == 'high_dividend_etf':
        etf_type_prefix = 'HighDividend_'
    elif config_type == 'industry_etf':
        etf_type_prefix = 'Industry_'
    else:
        etf_type_prefix = ''
    
    # Date range
    today = datetime.now()
    start_date_3y = (today - timedelta(days=3*365)).strftime('%Y-%m-%d')
    latest_date = today.strftime('%Y-%m-%d')
    
    # 對主動式 ETF 使用固定的起始日期（2025-07-22）
    if config_type == 'active_etf':
        start_date_3y = '2025-07-22'
        print(f"⚠️  主動式 ETF 使用固定起始日期: {start_date_3y}")
    
    print(f"\n🚀 開始執行 {config_type} 配置...")
    
    # 首先設定 matplotlib 後端
    print("  📊 設定 matplotlib 後端...")
    plt = setup_matplotlib_backend()

    # 1. 找出統一的比較期間
    print("  📅 查找統一比較期間...")
    # 主動式 ETF 使用固定的 7/22 起始日期，其他配置使用最晚上市日期
    use_fixed_start = (config_type == 'active_etf')
    common_start_date = find_common_start_date(etf_list, start_date_3y, latest_date, config_type, use_fixed_start=use_fixed_start)
    
    # 2. 下載0050作為基準（用於計算追蹤誤差）
    print(f"\n下載基準指數 0050...")
    benchmark_returns = None
    sp500_returns = None
    try:
        # 台股基準
        benchmark_df = download_price_data('0050.TW', start_date=common_start_date, end_date=latest_date, config_type=config_type)
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
        sp500_df = download_price_data('^GSPC', start_date=common_start_date, end_date=latest_date, config_type=config_type)
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
        data = get_etf_data(ticker, common_start_date, latest_date, benchmark_returns, risk_free_rate, config, config_type, annualize=should_annualize)
        if data:
            results.append(data)
    
    # 4. 顯示結果
    if results:
        df_results = pd.DataFrame(results)
        
        # Create 1-year and 3-year return dicts for charts
        ret_1y_dict = {}
        ret_3y_dict = {}
        for _, row in df_results.iterrows():
            ticker = row['證券代碼']
            ret_1y = row.get('1年年化報酬率 (%)', 'N/A')
            ret_3y = row.get('3年年化報酬率 (%)', 'N/A')
            ret_1y_dict[ticker] = float(ret_1y) if ret_1y != 'N/A' else 9999
            ret_3y_dict[ticker] = float(ret_3y) if ret_3y != 'N/A' else 9999
        
        # 不過濾 ETF - 全部顯示，1 年柱狀全部有，3 年柱狀只有成立滿 3 年的才有
        print(f"\n📊 分析完成")
        min_days_3years = 756  # 3 年 = 756 個交易日
        etf_3y_count = len(df_results[df_results['完整歷史天數'] >= min_days_3years])
        print(f"✅ 共分析 {len(df_results)} 支 ETF（其中 {etf_3y_count} 支滿足 3 年條件）")
        etf_filter_status = f"（共 {len(df_results)} 支，其中 {etf_3y_count} 支有 3 年數據）"
        
        # 按1年年化報酬率排序（3年年化有 N/A，改為9999無法正確排序，所以用1年）
        sort_column = '1年年化報酬率 (%)'  # 全部 ETF 都有1年數據
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
        return_col = '1年年化報酬率 (%)'
        numeric_returns = [x for x in df_results[return_col] if x != 'N/A']
        numeric_volatility = [x for x in df_results['年化波動率 (%)'] if x != 'N/A']
        
        return_label = '年化報酬率' if should_annualize else '績效'
        if numeric_returns:
            print(f"平均{return_label}: {np.mean(numeric_returns):.2f}%")
        if numeric_volatility:
            print(f"平均波動率: {np.mean(numeric_volatility):.2f}%")
            
        print(f"{'='*60}")

        # 5. 視覺化（暫時使用主程式內的函數，待重構）
        turnover_chart = plot_turnover_bar(df_results)
        print("\nChart.js 條形圖配置（換手率）：")
        print(turnover_chart)
        plot_price_trend({ticker: name for ticker, name in etf_list}, config, common_start_date, latest_date, etf_type_prefix)
        plot_radar_chart(df_results)
        print("\n折線圖已儲存為 etf_price_trend.png")
        print("雷達圖已儲存為 etf_radar_chart.png")

        print("\n📊 正在生成視覺化圖表...")
        
        # 修正字體問題的視覺化
        skip_plots = os.getenv('SKIP_PLOTS', '0') == '1'
        
        if not skip_plots:
            print("\n🎨 Generate charts...")
            try:
                generate_performance_chart(df_results, ret_1y_dict, ret_3y_dict, None, etf_type_prefix, output_folder)
                print("  ✅ Chart completed")
            except Exception as e:
                print(f"  ❌ Chart failed: {e}")
        else:
            print("\n⏭️  跳過圖表生成（SKIP_PLOTS=1）")
    else:
        print("沒有成功分析的ETF資料")