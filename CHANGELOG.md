# 更新紀錄

## 0.2.0 — 2026-11-07

- 新增 Windows 雙擊 start.bat 與互動選單：選擇模式、角色及任務來源。
- 新增 conversation 通用對話模式，保留 gpt 舊名稱作相容別名。
- 新增 --format text；選單同時輸出純文字與 JSON，結果集中於 outputs。
- 將 SS9012／5VCE 的板尺寸、線寬、版本與歷史環境移至獨立範例，不載入新任務。
- 通用轉角規則以專案明示條件為準，移除固定套用 45° 的預設。
- 測試由 17 項增至 26 項，涵蓋文字匯出、舊模式相容、互動選單與跨工作目錄啟動。
- JSON 狀態改為 needs_ai_work、needs_ai_decision、ai_handoff_ready；provider 正規化為 conversation。既有狀態解析程式需更新，退出碼規則不變。
