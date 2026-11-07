# PCB Local AI

[![Test and release](https://github.com/liu030308/pcb-local-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/liu030308/pcb-local-ai/actions/workflows/ci.yml) · [穩定版本下載](https://github.com/liu030308/pcb-local-ai/releases/latest) · GPL-3.0-only

以繁體中文協助 KiCad PCB 工作的可攜式 AI 技能包。可選擇本地模型，或將任務交給 ChatGPT、Claude、Gemini 等 AI 對話處理。

## 目前能做什麼

- 五種角色：零件、原理圖、PCB 布局、通用、獨立理論檢查。
- 自動解析目前使用者的專案／元件庫路徑，偵測 KiCad CLI。
- 有本地模型：呼叫本機 OpenAI 相容文字模型服務。
- 無本地模型：離線產生完整提示詞與規則，貼到你使用的 AI 對話即可。
- 保留工程證據要求，不將模型的 PASS 當作 ERC、DRC、模擬或量測結果。

這是文字助理、交接與工程檢查工具。已支援 KiCad CLI 的 ERC、DRC 與原理圖／PCB 一致性檢查；**尚未內建 KiCad 編輯、自動布局走線或角色自動調度。**

## 快速開始（Windows）

1. 按 GitHub 的 **Code → Download ZIP**，解壓縮整個資料夾。
2. 安裝 Python 3.10 或以上；不需要第三方 Python 套件。
3. 雙擊 **`start.bat`**，首次啟動先完成環境設定精靈，再選「建立任務」。
4. 選「有本地模型」或「其他 AI（無本地模型）」，再選工作角色。
5. 直接輸入需求（單獨輸入 `.` 結束），或輸入／拖入 UTF-8 任務檔路徑。
6. 結果存放在 `outputs`：`.txt` 可直接複製，`.json` 留存角色及處理狀態。每次使用不同檔名。

選「其他 AI」時，開啟 `.txt`，複製全文貼到你使用的 AI 對話。不必從 JSON 抽出 prompt，也不需本地模型或 API key。程式不會自動傳送任務。

選單也能切換預設模式、查看自動路徑、重跑環境設定精靈及執行工程檢查。啟動檔會尋找 Python，缺少或版本不足時顯示提示；程式不會自動安裝工具。

KiCad 只有在實際 EDA 作業時才需要。找不到的工具會保持空值。

### 命令列使用

```powershell
python scripts/menu.py
python scripts/local_worker.py setup
python scripts/local_worker.py configure
python scripts/local_worker.py paths
python scripts/local_worker.py doctor
```

### 無本地模型

```powershell
python scripts/local_worker.py work --provider conversation --role theory --task-file examples/task.txt --format text --output prompt.txt
```

開啟 `prompt.txt`，複製全文到 ChatGPT、Claude、Gemini 或其他 AI 對話；支援讀檔的 AI 也可直接讀取。移除 `--format text` 即輸出 JSON，適合其他程式串接。

本命令不呼叫任何 AI、不需要 API key。退出碼 **3** 表示等待 AI 對話承接，並非設計完成或執行錯誤。

### 有本地模型

啟動支援 `/v1/models` 與 `/v1/chat/completions` 的本機服務，預設位址為 `http://127.0.0.1:8686/v1`。若埠不同，修改 config.json 的 base_url。

```powershell
python scripts/local_worker.py work --provider local --role parts --task-file examples/task.txt --output result.json
```

`model: null` 採用服務唯一已載入的模型；有多個模型時請指定正確模型 ID。服務失敗不會自動改用雲端。

## 設定與可攜性

- config.json 的路徑保持 `null`，每台電腦執行時會重新偵測，不會寫入發布者帳號。
- 專案預設 `~/PCB-Projects`，元件庫預設 `~/Datasheet`；目錄不會自動建立。
- 可手動指定路徑；相對路徑以 config.json 所在資料夾為基準。
- 非標準 KiCad 安裝位置可手動填入 kicad_cli。自動偵測以 Windows 為主；其他系統可透過 PATH 或明確設定使用 CLI，尚未完成跨平台實機驗證。
- `--provider local`／`--provider conversation` 僅覆寫單次命令；`configure` 會儲存選擇。
- 退出碼：0=完成本次命令；1=錯誤；3=等待對話處理。

## 給 AI 工具使用

支援技能的工具可讀取 [SKILL.md](SKILL.md)，其他工具可將其作為操作指引。SS9012／5VCE 的歷史規格已移至 [獨立範例](examples/ss9012-history.md)，僅延續該專案時參考，不會自動加入新任務。實際操作能力取決於 AI 工具提供的檔案、搜尋、計算與 EDA 權限。

分享前請檢查任務與交接檔是否含個人資料或未公開電路；交接內容包含解析後的本機路徑。

## 測試

```powershell
python -B -m unittest discover -s scripts -p "test_*.py" -v
```

目前有 76 項本機測試，涵蓋路徑解析、模式選擇、離線交接及本地請求邊界。測試通過不代表電路已通過工程驗證。

## 舊版相容

舊的 `--provider gpt` 與 config.json 中的 `"routine_work_provider": "gpt"` 仍可使用，會解析為 `conversation`。

JSON 交接狀態由 `needs_gpt_work`／`needs_gpt_decision` 改為 `needs_ai_work`／`needs_ai_decision`，環境檢查的對話模式狀態改為 `ai_handoff_ready`；有解析這些欄位的程式需同步更新。等待交接的退出碼仍為 3。

## 首次環境設定

```powershell
python scripts/local_worker.py setup
```

設定精靈可選模式、KiCad CLI、專案／元件庫目錄；本地模式另外設定服務位址與模型 ID。Enter 保留，路徑輸入 `:auto` 恢復自動。儲存前列出診斷結果，可選擇是否建立資料目錄；不會自動安裝軟體。

「未偵測到」表示可能尚未安裝或不在搜尋範圍；「設定路徑不存在」則應修正設定。其他 AI 模式不檢查模型服務；本地服務失敗仍會保留其他工具的診斷結果。透過管線執行選單時不強制啟動首次精靈。

## KiCad 工程檢查

從選單選「執行 KiCad 工程檢查」，或：

```powershell
python scripts/validate_project.py --project "你的專案/電路.kicad_pro" --rules-file "你的專案/validation-rules.json"
```

專案需有同目錄、同名的 `.kicad_sch`／`.kicad_pcb`，並安裝支援相關參數的 KiCad CLI（以 KiCad 8+ 介面實作，執行時探測能力）。模型服務不是必要條件。

依 [KiCad 官方 CLI 文件](https://docs.kicad.org/10.0/en/cli/cli.html) 執行 ERC、DRC 與 schematic parity，包含錯誤和警告；不使用 `--save-board`。每次建立新的證據目錄，保存原始 JSON、命令、返回碼、工具輸出、版本與 SHA-256，並檢查專案、同目錄樹原理圖、PCB 與同名自訂規則檔是否改變。外部庫等依賴不在這份雜湊清單內。

複製 [幾何規則範本](examples/validation-rules.json) 到自己的專案，填入經確認的條件：

- `min_track_width_mm`：未另設網路門檻時的預設最小走線寬；`per_net_min_width_mm`：特定網路的最小走線寬。
- `allowed_track_layers`：允許的走線銅層，例如 `["B.Cu"]`，不等於完整實體銅層檢查。
- `allowed_segment_headings_deg`：允許直線方向，以 180° 為週期；不檢查焊盤外連續轉彎，遇圓弧列待確認。
- `max_vias`：最大過孔數；`outline_size_mm`：`[寬, 高]`，本版只自動量測單一 `gr_rect` 板框。

範本預設 null，不替新電路決定數值。未指定幾何門檻、缺少工具／檔案或不支援的形狀，結果為 `needs_review`；錯誤或違規為 `fail`。`checks_passed` 僅表示這次已實作的檢查通過，**engineering_release_approved 永遠為 false**。仍需功能理論／模擬、量測、完整 courtyard／製造層及板廠驗證；也應檢閱 KiCad 被忽略或排除的規則。

驗證命令退出碼：0=本次檢查通過；1=違規或執行錯誤；3=尚待確認。結果寫入 `outputs/validation-*/summary.json`。使用 `--output-dir` 時須指定尚不存在的新目錄，以免重用舊報告。

## 版本、自動測試與發布

GitHub Actions 會執行 Windows／Linux、Python 3.10／3.13 測試；另以 KiCad 官方穩定版 PPA 的真正 KiCad 執行空白與故意錯誤的暫存專案。這只驗證檢查流程，不是產品電路驗證。

維護者更新 VERSION、CHANGELOG.md 與 docs/RELEASE_NOTES.md 後，推送相符的 `v版本號` 標籤；測試全部成功後才建立 Release，附乾淨設定的 ZIP 與 SHA256SUMS。一般使用者無需設定 GitHub token。

```powershell
python scripts/build_release.py
```

發布包只附 `config.example.json`，首次啟動建立個人 config.json；不包含現用設定、工作階段、遷移備份、outputs 或 Python 快取；相同來源可重現相同 ZIP。分享請優先使用 Release 的發布包。

## 授權

本專案依 **GPL-3.0-only** 發布，完整條款見 [LICENSE](LICENSE)。Copyright (C) 2026 PCB Local AI contributors。GPL 授權適用於本專案程式與文件；KiCad 及各 AI 服務另有自己的授權與使用條款。

## 0.4 設定與狀態遷移

儲存庫與發布包不再追蹤／附帶 config.json。首次啟動由同目錄 config.example.json 初始化；若已存在個人設定，絕不以範本覆蓋。環境設定仍保留原有平面欄位，避免強迫使用者改寫舊設定。

作用中專案、PCB、版本、專案名稱與 accepted_projects 改存於同目錄的 `.pcb_state.json`。首次讀取舊設定時會自動備份為 `.config.pre-state-migration.json`，再遷移動態欄位；已有狀態以既有狀態檔為準，舊值保留在備份中。設定及狀態寫入使用暫存檔與原子替換。自訂 `--config other.json` 使用獨立的 `.other_state.json`，避免共用同一工作階段。

**從舊的 Git clone 更新前，先備份自己的 config.json。** 本次停止追蹤既有設定檔，Git 更新可能對舊的本機修改提出衝突；更新後將個人設定放回原位置，再啟動程式遷移。直接下載新 ZIP 的使用者，可將舊 config.json 複製進新資料夾；不要把範本覆寫到個人設定。

## 本地推論串流與逾時

預設保留非串流相容模式。環境精靈可設定串流，也可單次切換：

```powershell
python scripts/local_worker.py work --provider local --stream --task-file examples/task.txt --output result.json
python scripts/local_worker.py work --provider local --no-stream --task-file examples/task.txt --output result.json
```

設定中的 `stream` 使用 true／false。串流預覽在 CLI 寫到 stderr，stdout 保持完整 JSON 或文字；選單顯示預覽後另存最終結果。只有收到 finish_reason=stop、[DONE] 且有文字才成功；錯誤、截斷、斷線、逾時或取消不產生新的成功結果檔，也不自動回退重試。不支援 SSE 的服務請明確使用 --no-stream。

- `connect_timeout_seconds`：每次 HTTP 連線等待，預設 10 秒。
- `read_timeout_seconds`：網路閒置讀取等待，預設 180 秒；舊設定未提供時沿用 timeout_seconds。
- `total_timeout_seconds`：每次 HTTP 請求的總時間上限，預設 900 秒；即使持續收到心跳也不會無限等待。查模型列表與推論是不同請求。

仍只連線本機 HTTP，不使用代理、不跟隨重新導向、不呼叫雲端 API。取消 CLI 輸出退出碼為 130。控制協定以 [Python HTTP client](https://docs.python.org/3/library/http.client.html) 與 [SSE 事件格式](https://html.spec.whatwg.org/multipage/server-sent-events.html) 為參考；本工具不是會自動重新連線的瀏覽器 EventSource。

## 規則預檢與解析樣本

schemas/validation-rules.schema.json 定義可執行幾何規則；schemas/kicad-erc-report.schema.json 與 kicad-drc-report.schema.json 檢查本工具消費的報告結構與欄位。內建驗證器僅實作這些 schema 所使用的關鍵字，不是完整的通用 JSON Schema 引擎，也不宣稱涵蓋上游所有可選欄位。

自訂規則在任何 KiCad 命令啟動前先驗證；型別錯誤、未知欄位與非有限數值都攔下。報告檢查必要來源／版本、頁面、違規種類、嚴重性與受影響物件；缺漏不當作零錯誤。工程提示詞規範與可執行數值規則仍分開維護，不能以提示詞取代實際證據。

examples/fixtures 包含 PCB 解析樣本與故意錯誤的雙頁原理圖。board_audit 只解析 PCB；階層式原理圖及子頁未接腳位由真正 KiCad ERC 的整合測試處理。複雜 Edge.Cuts 仍列待確認，並未因新增樣本就宣稱支援所有板框。
