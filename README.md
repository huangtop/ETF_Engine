# ETF Engine - 台湾 ETF 性能分析工具

### 基本使用
```bash
# 分析主动式 ETF（默认）
python ETFEngine_main.py active_etf

# 分析高股息 ETF
python ETFEngine_main.py high_dividend_etf

# 分析股息 ETF
python ETFEngine_main.py dividend_etf

# 分析美股 ETF
python ETFEngine_main.py us_etf
```

## 📁 项目结构

```
ETF_Engine/
├── ETFEngine_main.py              # 主程序
├── config_loader.py               # 配置加载器
├── font_config.py                 # 字体配置
├── get_twse_dividend.py           # 股息数据获取
├── twse_dividend.py               # TWSE 接口
├── etf_configs/                   # ETF 配置文件
│   ├── active_etf.json            # 主动式 ETF
│   ├── high_dividend_etf.json     # 高股息 ETF
│   ├── dividend_etf.json          # 股息 ETF
│   └── us_etf.json                # 美股 ETF
└── Output_*/                      # 输出文件夹
```
