# Render Deploy Configuration
# 此文件用于在 Render 上配置自動部署

## Render Deploy Hook 設置步驟

### 1. 在 Render 創建 Web Service
- 連接你的 GitHub 倉庫
- 選擇 Python 作為運行時
- 設置構建命令：`pip install -r requirements.txt`
- 設置啟動命令（如果有 Web 服務）

### 2. 獲取 Deploy Hook URL
1. 進入 Render Dashboard
2. 找到你的 Service
3. 進入 Settings → Deploy hooks
4. 創建一個新的 Deploy Hook
5. 複製 Hook URL

### 3. 在 GitHub 配置 Secret
1. 進入 GitHub 倉庫 → Settings → Secrets and variables → Actions
2. 創建新的 Repository Secret，命名為 `RENDER_DEPLOY_HOOK`
3. 粘貼你的 Render Deploy Hook URL

### 4. 驗證 Workflow
- Workflow 會在每週一凌晨 2 點 (UTC) 自動運行
- 或者在 Actions 標籤頁手動觸發 "Weekly Update ETF Charts"

## 文件結構
```
.github/
├── workflows/
│   └── update-charts.yml    # GitHub Actions Workflow
└── README.md                # 本文件

charts_output/               # 部署到 Render 的圖表
├── *.png                    # 生成的 PNG 圖表
├── *.csv                    # 分析結果 CSV
└── UPDATE_TIME.txt          # 更新時間戳記
```

## 故障排查

### Workflow 未執行
- 檢查 GitHub Actions 是否已啟用
- 檢查 `.github/workflows/update-charts.yml` 語法
- 查看 Actions 標籤頁的日誌

### Render 部署未觸發
- 驗證 `RENDER_DEPLOY_HOOK` Secret 是否正確設置
- 檢查 Hook URL 是否有效
- 查看 Workflow 日誌中的錯誤信息

### 圖表生成失敗
- 檢查 Python 依賴是否正確安裝
- 查看日誌中的錯誤信息
- 驗證 yfinance 是否能正常下載數據

## 安全建議

1. **保護 Deploy Hook URL**
   - 使用 GitHub Secrets 存儲，不要在代碼中硬編碼
   - 定期輪換 Hook URL

2. **限制 Workflow 權限**
   - 使用最小權限原則
   - 定期檢查 Workflow 日誌

3. **監控部署**
   - 在 Render 設置通知
   - 定期檢查部署状態

## 自定義 Schedule

編輯 `.github/workflows/update-charts.yml` 中的 `cron` 表達式：

```yaml
on:
  schedule:
    # Cron 格式: 分 小時 日 月 星期
    # 每週一凌晨 2 點 (UTC)
    - cron: '0 2 * * 1'
    
    # 其他示例:
    # 每天早上 8 點 (台灣時間) = UTC 0 點
    # - cron: '0 0 * * *'
    
    # 每週五下午 5 點 (UTC)
    # - cron: '0 17 * * 5'
```

## 監控和告警

### 在 Render 上添加通知
1. Settings → Notifications
2. 配置郵件或 Slack 通知
3. 選擇 "Deploy events"

### GitHub Actions 通知
- Actions 失敗時，GitHub 會發送郵件通知
- 可在個人設置中配置通知偏好

---
**最後更新**: 2025-12-23
**版本**: 1.0
