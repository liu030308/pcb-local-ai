---
name: pcb-local-ai
description: Assist KiCad PCB tasks with optional local inference or handoff to any AI conversation, preserving project-specific requirements and tool evidence.
---

# PCB AI 工作助理

協助零件資料、原理圖、布局與理論審閱。開始前確認使用者的電路需求、工作模式與可用工具。專案資料不足時標記 NEEDS_DATA，不猜測腳位、規格、製程或核定條件。

## 開始使用

Windows 使用者可雙擊 `start.bat`，選擇模式、角色，再輸入需求或提供 UTF-8 任務檔。也可執行 `python scripts/menu.py`。所有指令路徑以下均相對技能根目錄。

- `local`：本機 OpenAI 相容文字服務。預設 `http://127.0.0.1:8686/v1`；失敗就回報，不自動切換模型或對話供應者。
- `conversation`：其他 AI，無需本地模型。腳本只產生交接內容，不會呼叫雲端 API、登入對話或自動傳送任務。由目前協調者承接，或讓使用者將文字貼到選用的 AI。
- 舊名稱 `gpt` 仍是 conversation 的相容別名；設定載入後會正規化為 conversation。

```powershell
python scripts/local_worker.py configure
python scripts/local_worker.py paths
python scripts/local_worker.py doctor
python scripts/local_worker.py work --provider conversation --role theory --task-file examples/task.txt --format text --output prompt.txt
python scripts/local_worker.py work --provider local --role general --task-file examples/task.txt --output result.json
python scripts/local_worker.py decision --task-file examples/task.txt --format text --output decision.txt
```

`configure` 儲存預設模式，`--provider` 只覆寫單次命令。`paths` 離線顯示解析後設定，不建立資料夾、不改寫設定。`doctor` 在 local 模式查模型服務及工具路徑，在 conversation 模式不查本地模型；均不代表已測試推論或 EDA。

`work` 預設輸出 JSON；`--format text` 輸出可直接複製的完整提示詞（conversation）或模型草稿（local）。選單同時儲存文字與 JSON 到技能根目錄的 outputs，以時間命名，不自動覆蓋舊任務。

退出碼 0 代表命令已完成，1 為錯誤，3 為需要對話承接。conversation 的 work 狀態是 needs_ai_work；decision 狀態是 needs_ai_decision。退出碼 3 不代表設計完成。承接對話後將決策與來源加入後續任務。

## 五種角色與分工

- `parts`：先查設定中的索引與本地資料，缺項才提出原廠 Datasheet 搜尋工作；核對完整料號、腳位、封裝及尺寸，未驗證草稿放 staging。
- `schematic`：依原始需求與已驗證元件整理連線與草稿；缺件交零件角色，布局交布局角色。
- `layout`：依實際網路、板框、固定元件與專案規則提出擺放／走線草稿；轉角、層數、線寬等以該專案需求為準。
- `general`：檔案整理、格式轉換、索引與報告；專業工作以 HANDOFF 列出角色與必要背景。
- `theory`：依原始需求、Datasheet、實際值與匯出網路獨立檢查，不把設計角色的結論當證據。

每次只加入所選角色的指令，不共享角色對話歷史。HANDOFF、NEEDS_DATA、FAIL、NEEDS_DECISION 由調用者處理，沒有自動角色調度或工具迴圈。抉擇衝突交協調對話，不能自行改變使用者已核定條件。

## 電路與 PCB 驗證

開始電路設計前，主動取得原廠資料與理論來源，保存完整料號、版本、腳位、封裝及來源。先釐清供電、訊號幅度／頻率、負載、增益、尺寸、層數與製程條件；缺項明列。

理論檢查涵蓋 KCL/KVL、極性、偏壓與工作區、額定／功耗、電流回路、共地／隔離、輸入輸出分離、阻抗、耦合、負載、增益、頻寬與失真。寫出有符號方程並由精確計算或模擬驗證殘差；穩態直流把耦合電容視為開路，分別求解兩側回路。

規則位於 `rules/pcb_requirements.json`，專業角色會自動附加。依使用者核定的銅厚、溫升、工作電流、線長、壓降與板廠下限計算每網路線寬；不用元件絕對最大電流代替耗流。依實際專案檢查間距、孔徑／環寬、板邊、courtyard、絲印、製造層與回流。45° 只有在專案要求時才是驗收條件；單面、無過孔、無跳線等限制須由該專案確認。

理論、ERC、DRC、原理圖／PCB 一致性、實際網路、線寬／轉角、板框／courtyard、實體層與 Gerber 是各自的證據，不能互相替代。模型 PASS 或另一個 AI 同意都不是工具執行或工程驗證證明；有錯列 FAIL，缺證據列待確認，不宣稱全面符合 IPC、板廠 DFM 或實測結果。

模型輸出為待驗證草稿，不直接 eval、exec 或作為 shell 命令執行。原設計保留，修改輸出副本。完成後是否開啟 KiCad，依使用者要求及 open_completed_project/open_completed_pcb 設定由協調者執行，不能捨棄未儲存修改。

## 路徑與元件庫

路徑保持 null 可跨帳號使用，執行時自動解析。project_root 預設 `~/PCB-Projects`，component_library_root 預設 `~/Datasheet`；個人資料集中管理，內建庫保留安裝位置。

- `Datasheets`：原廠資料；`KiCad/symbols`、`KiCad/footprints`、`KiCad/3dmodels`：個人庫。
- `staging`：未驗證下載或草稿；`index/library-index.json`：共同搜尋索引，不代表已驗證。
- 新增／更新庫後由工具重建索引，註冊新庫前備份全域清單至 `<component_library_root>/index/backups`。本包未內建索引建立或庫註冊工具。

KiCad 明確設定優先，其次 PATH，再查 ProgramFiles/KiCad 與 LOCALAPPDATA/Programs/KiCad 的版本目錄；選最高版本 CLI。builtin_library_root 由 CLI 推導且需存在；非標準安裝請手動指定。

路徑可用 `~`、環境變數或相對路徑；相對路徑以設定檔目錄為基準。Windows JSON 路徑可用 `/` 或跳脫反斜線。模型 ID 不當作路徑解析；model=null 僅在服務載入唯一模型時自動選用，多模型需指定 ID。

新電腦不繼承其他人的 active_project、active_pcb、核定版本或已註冊庫狀態；不自動猜選電路，也不搬移舊檔案。只有使用者要求延續／核對 SS9012 或 5VCE 歷史專案時，才讀取 [歷史專案參考](examples/ss9012-history.md)，並重新核對實際檔案；其中數值不是通用預設。

## 實作邊界

腳本需要 Python 3.10 以上且無第三方依賴。已有文字角色、模式選擇、交接、純文字輸出與路徑偵測；未內建 KiCad 編輯、布局走線、ERC/DRC、搜尋下載、數值模擬或桌面操作。實際 EDA 工作仍需安裝 KiCad 與具備相應工具的協調者。本地文字介面不能直接處理圖片或 PDF 電路辨識。
