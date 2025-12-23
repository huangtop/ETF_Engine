# ETF Engine - GitHub Actions & Render 部署指南

## 📋 目錄
1. [快速入門](#快速入門)
2. [本地運行](#本地運行)
3. [GitHub Actions 配置](#github-actions-配置)
4. [Render 部署](#render-部署)
5. [故障排查](#故障排查)

---

## 快速入門

### 前置條件
- Python 3.10+
- Git
- GitHub 帳戶
- Render 帳戶（可選，用於自動部署）

### 一次性設置步驟

#### 1. 克隆倉庫
```bash
git clone <your-repo-url>
cd ETF_Engine
```

#### 2. 創建 Python 虛擬環境
```bash
python -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

#### 3. 安裝依賴
```bash
pip install -r requirements.txt
```

#### 4. 在本地測試
```bash
# 生成所有配置的圖表
python generate_all_charts.py

# 或生成特定配置
python ETFEngine_main.py active_etf
python ETFEngine_main.py high_dividend_etf
python ETFEngine_main.py industry_etf
```

---

## 本地運行

### 生成所有 ETF 圖表

```bash
# 完整批量生成
python generate_all_charts.py

# 輸出將保存到 charts_output/ 文件夾
```

### 生成特定配置的圖表

```bash
# 主動式 ETF
python ETFEngine_main.py active_etf
# 輸出: Output_Active_ETF/

# 高股息 ETF
python ETFEngine_main.py high_dividend_etf
# 輸出: Output_HighDividend_ETF/

# 產業型 ETF
python ETFEngine_main.py industry_etf
# 輸出: Output_Industry_ETF/
```

### 更新費用率

```bash
# 更新所有配置的費用率
python fetch_expense_ratio.py active_etf --no-yfinance
python fetch_expense_ratio.py high_dividend_etf --no-yfinance
python fetch_expense_ratio.py industry_etf --no-yfinance
```

---

## GitHub Actions 配置

### 1. 上傳至 GitHub

```bash
git add .github/workflows/update-charts.yml
git add requirements.txt
git add generate_all_charts.py
git commit -m "feat: add GitHub Actions workflow for weekly chart updates"
git push origin main
```

### 2. 驗證 Workflow 文件

檢查 `.github/workflows/update-charts.yml` 是否正確：

```bash
# 驗證 YAML 語法（可選）
pip install yamllint
yamllint .github/workflows/update-charts.yml
```

### 3. 在 GitHub 上啟用 Actions

1. 進入你的 GitHub 倉庫
2. 點擊 **Actions** 標籤
3. 確保 Actions 已啟用（應該看到 "All workflows are active"）

### 4. 手動觸發 Workflow（測試）

1. 進入 **Actions** 標籤
2. 在左側選擇 **Weekly Update ETF Charts**
3. 點擊 **Run workflow**
4. 選擇 **main** 分支
5. 點擊 **Run workflow** 按鈕

---

## Render 部署

### 1. 在 Render 上創建 Web Service

#### 選項 A：連接 GitHub 倉庫（推薦）

1. 進入 [Render Dashboard](https://dashboard.render.com)
2. 點擊 **New +**
3. 選擇 **Web Service**
4. 連接你的 GitHub 帳戶和倉庫
5. 配置如下：
   - **Name**: `etf-engine` (或自定義)
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python generate_all_charts.py` (或保留為空如果只用於 Hook)

#### 選項 B：使用 Deploy Hook（推薦用於定時更新）

這是推薦方式，因為不需要持續運行服務器。

### 2. 創建 Deploy Hook

1. 在 Render Dashboard 中找到你的 Service
2. 進入 **Settings**
3. 找到 **Deploy** 部分
4. 點擊 **Create Deploy Hook**
5. 設置如下：
   - **Name**: ETF Charts Update
   - **Branch**: main
6. 複製生成的 Hook URL（看起來像 `https://api.render.com/deploy/srv-...`)

### 3. 在 GitHub 配置 Secret

1. 進入你的 GitHub 倉庫
2. 點擊 **Settings** → **Secrets and variables** → **Actions**
3. 點擊 **New repository secret**
4. 配置如下：
   - **Name**: `RENDER_DEPLOY_HOOK`
   - **Secret**: 粘貼你從 Render 複製的 Hook URL
5. 點擊 **Add secret**

### 4. 驗證部署

在 GitHub Actions 中手動觸發 workflow：

```
✅ 看到 "Trigger Render deployment" 步驟成功執行
✅ 在 Render Dashboard 中看到新的部署開始
```

---

## 故障排查

### Workflow 未執行

**檢查清單:**
- [ ] `.github/workflows/update-charts.yml` 文件存在且語法正確
- [ ] GitHub Actions 已在倉庫設置中啟用
- [ ] 倉庫已推送到 main 分支

**解決方案:**
```bash
# 檢查 workflow 文件
ls -la .github/workflows/

# 確保提交到 main 分支
git push origin main

# 在 GitHub Actions 中手動觸發測試
```

### Render 部署未觸發

**檢查清單:**
- [ ] `RENDER_DEPLOY_HOOK` Secret 已在 GitHub 中設置
- [ ] Hook URL 正確無誤
- [ ] Hook URL 仍然有效（未過期）

**解決方案:**
```bash
# 測試 Hook URL（本地運行）
curl -X POST "你的-hook-url"

# 如果收到 404，需要重新創建 Hook
```

### 圖表生成失敗

**檢查日誌:**
1. 進入 GitHub Actions
2. 點擊失敗的 Workflow Run
3. 查看 **Generate Active ETF Charts** 等步驟的日誌

**常見問題:**
- yfinance 無法下載數據 → 等待數天，數據可能延遲
- Python 版本不兼容 → 確保 Python 3.10+
- 依賴未安裝 → 檢查 requirements.txt

### 本地測試失敗

```bash
# 清除快取並重新運行
rm -rf Output_*_ETF/ charts_output/
python generate_all_charts.py

# 檢查錯誤信息
python -c "import yfinance; print(yfinance.__version__)"
```

---

## 日程配置

### 修改更新時間

編輯 `.github/workflows/update-charts.yml`：

```yaml
on:
  schedule:
    # Cron 語法: 分 小時 日 月 星期
    # 星期: 0=週日, 1=週一, ..., 6=週六
    
    # 每週一凌晨 2 點 (UTC)
    - cron: '0 2 * * 1'
    
    # 每天早上 8 點 (台灣時間) = UTC 0 點
    # - cron: '0 0 * * *'
    
    # 每週三、五下午 3 點 (UTC)
    # - cron: '0 15 * * 3,5'
```

**時區轉換:**
- UTC 0:00 = 台灣時間 08:00
- UTC 2:00 = 台灣時間 10:00
- UTC 10:00 = 台灣時間 18:00

---

## 監控和告警

### 在 GitHub 中配置通知

1. **Settings** → **Notifications**
2. 選擇 "Watching" 此倉庫
3. 啟用 "Workflows" 通知

### 在 Render 中配置通知

1. Render Dashboard → **Account** → **Notifications**
2. 設置郵件或 Slack 通知
3. 選擇 "Deploy events"

---

## 檔案結構

```
ETF_Engine/
├── .github/
│   ├── workflows/
│   │   └── update-charts.yml       # GitHub Actions Workflow
│   └── DEPLOY_SETUP.md             # 詳細設置指南
├── etf_configs/
│   ├── active_etf.json
│   ├── high_dividend_etf.json
│   └── industry_etf.json
├── Output_*_ETF/                   # 生成的圖表（輸出）
├── charts_output/                  # 收集的輸出（供部署）
├── ETFEngine_main.py               # 主分析腳本
├── generate_all_charts.py          # 批量生成腳本
├── fetch_expense_ratio.py          # 費用率更新工具
├── requirements.txt                # Python 依賴
├── .gitignore
└── README.md
```

---

## 下一步

- [ ] 在本地運行 `python generate_all_charts.py` 測試
- [ ] 推送代碼到 GitHub
- [ ] 在 GitHub Actions 中手動觸發 Workflow
- [ ] 創建 Render Deploy Hook
- [ ] 在 GitHub 中設置 `RENDER_DEPLOY_HOOK` Secret
- [ ] 驗證週期性運行（下次在排定時間檢查）

---

**有問題？** 檢查 [故障排查](#故障排查) 部分或查看 GitHub Actions 日誌。

**最後更新:** 2025-12-23  
**版本:** 1.0
