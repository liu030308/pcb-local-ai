# 更新紀錄

## 0.4.0 — 2026-11-07

- config.json 退出版控與發布包，首次由範本初始化；保留既有個人設定。
- 動態專案狀態遷移至 .pcb_state.json，先備份、既有狀態優先、原子寫入。
- 新增可選 SSE 預覽、連線／閒置／總逾時；完整終止前不保存成功結果。
- 新增幾何規則 Schema 預檢、ERC／DRC 報告結構驗證與 PCB 專屬解析樣本。
- 新增階層原理圖及子頁未接腳位的真實 KiCad 整合測試。
- 本機測試由 49 項增至 76 項，含實際 loopback HTTP／SSE 連線。

## 0.3.0 — 2026-11-07

- 首次環境設定精靈與完整診斷，支援重設自動路徑與可選建立資料目錄。
- 新增真實 KiCad ERC／DRC／schematic parity 證據流程與明確的幾何檢查範圍。
- 報告保存指令、返回碼、stdout／stderr、版本與輸入／報告雜湊，不自動授權工程放行。
- 加入 GPL-3.0-only 授權。
- 新增跨平台 GitHub Actions、真實 KiCad 整合測試、版本標籤發布與可重現乾淨 ZIP／SHA256SUMS。

## 0.2.0 — 2026-11-07

- 新增 Windows 雙擊 start.bat 與互動選單：選擇模式、角色及任務來源。
- 新增 conversation 通用對話模式，保留 gpt 舊名稱作相容別名。
- 新增 --format text；選單同時輸出純文字與 JSON，結果集中於 outputs。
- 將 SS9012／5VCE 的板尺寸、線寬、版本與歷史環境移至獨立範例，不載入新任務。
- 通用轉角規則以專案明示條件為準，移除固定套用 45° 的預設。
- 測試由 17 項增至 26 項，涵蓋文字匯出、舊模式相容、互動選單與跨工作目錄啟動。
- JSON 狀態改為 needs_ai_work、needs_ai_decision、ai_handoff_ready；provider 正規化為 conversation。既有狀態解析程式需更新，退出碼規則不變。
