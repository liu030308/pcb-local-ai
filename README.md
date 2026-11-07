# PCB Local AI

以繁體中文協助 KiCad PCB 工作的可攜式 AI 技能包。可選擇本地模型，或將任務交給 ChatGPT、Claude、Gemini 等 AI 對話處理。

## 目前能做什麼

- 五種角色：零件、原理圖、PCB 布局、通用、獨立理論檢查。
- 自動解析目前使用者的專案／元件庫路徑，偵測 KiCad CLI。
- 有本地模型：呼叫本機 OpenAI 相容文字模型服務。
- 無本地模型：離線產生完整提示詞與規則，貼到你使用的 AI 對話即可。
- 保留工程證據要求，不將模型的 PASS 當作 ERC、DRC、模擬或量測結果。

這是文字助理與交接工具。**尚未內建 KiCad 編輯、自動布局走線、ERC/DRC 執行或角色自動調度。**

## 快速開始（Windows）

1. 按 GitHub 的 **Code → Download ZIP**，解壓縮整個資料夾。
2. 安裝 Python 3.10 或以上；不需要第三方 Python 套件。
3. 雙擊 **`start.bat`**，選「建立任務」。
4. 選「有本地模型」或「其他 AI（無本地模型）」，再選工作角色。
5. 直接輸入需求（單獨輸入 `.` 結束），或輸入／拖入 UTF-8 任務檔路徑。
6. 結果存放在 `outputs`：`.txt` 可直接複製，`.json` 留存角色及處理狀態。每次使用不同檔名。

選「其他 AI」時，開啟 `.txt`，複製全文貼到你使用的 AI 對話。不必從 JSON 抽出 prompt，也不需本地模型或 API key。程式不會自動傳送任務。

選單也能切換預設模式、查看自動路徑及檢查環境。啟動檔會尋找 Python，缺少或版本不足時顯示提示；程式不會自動安裝工具。

KiCad 只有在實際 EDA 作業時才需要。找不到的工具會保持空值。

### 命令列使用

```powershell
python scripts/menu.py
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

目前有 26 項測試，涵蓋路徑解析、模式選擇、離線交接及本地請求邊界。測試通過不代表電路已通過工程驗證。

## 舊版相容

舊的 `--provider gpt` 與 config.json 中的 `"routine_work_provider": "gpt"` 仍可使用，會解析為 `conversation`。

JSON 交接狀態由 `needs_gpt_work`／`needs_gpt_decision` 改為 `needs_ai_work`／`needs_ai_decision`，環境檢查的對話模式狀態改為 `ai_handoff_ready`；有解析這些欄位的程式需同步更新。等待交接的退出碼仍為 3。
