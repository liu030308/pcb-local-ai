# PCB Local AI

以繁體中文協助 KiCad PCB 工作的可攜式 AI 技能包。可選擇本地模型，或將任務交給 ChatGPT、Claude、Gemini 等 AI 對話處理。

## 目前能做什麼

- 五種角色：零件、原理圖、PCB 布局、通用、獨立理論檢查。
- 自動解析目前使用者的專案／元件庫路徑，偵測 KiCad CLI。
- 有本地模型：呼叫本機 OpenAI 相容文字模型服務。
- 無本地模型：離線產生完整提示詞與規則，貼到你使用的 AI 對話即可。
- 保留工程證據要求，不將模型的 PASS 當作 ERC、DRC、模擬或量測結果。

這是文字助理與交接工具。**尚未內建 KiCad 編輯、自動布局走線、ERC/DRC 執行或角色自動調度。**

## 快速開始

1. 按 GitHub 的 **Code → Download ZIP**，解壓縮。
2. 安裝 Python 3.10 或以上，於本資料夾開啟終端機。不需要安裝第三方 Python 套件。
3. 選擇工作模式：

```powershell
python scripts/local_worker.py configure
```

輸入 `1`：有本地模型。輸入 `2`：無本地模型，交給 AI 對話。程式會記住你的選擇。

4. 檢查解析結果與環境：

```powershell
python scripts/local_worker.py paths
python scripts/local_worker.py doctor
```

KiCad 只有在實際 EDA 作業時才需要。找不到的工具會保持空值，不會自動安裝。

### 無本地模型

```powershell
python scripts/local_worker.py work --provider gpt --role theory --task-file examples/task.txt --output handoff.json
```

開啟 `handoff.json`，將 `prompt` 的內容貼到 ChatGPT、Claude、Gemini 或其他 AI 對話；支援讀檔的 AI 也可直接讀取交接檔。`gpt` 是對話交接模式的名稱，不限 OpenAI 模型。

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
- `--provider local`／`--provider gpt` 僅覆寫單次命令；`configure` 會儲存選擇。
- 退出碼：0=完成本次命令；1=錯誤；3=等待對話處理。

## 給 AI 工具使用

支援技能的工具可讀取 [SKILL.md](SKILL.md)，其他工具可將其作為操作指引。當中的 SS9012／5VCE 規格為歷史專案條件，不是新使用者的核定需求。實際操作能力取決於 AI 工具提供的檔案、搜尋、計算與 EDA 權限。

分享前請檢查任務與交接檔是否含個人資料或未公開電路；交接內容包含解析後的本機路徑。

## 測試

```powershell
python -B -m unittest discover -s scripts -p "test_*.py" -v
```

目前有 17 項單元測試，涵蓋路徑解析、模式選擇、離線交接及本地請求邊界。測試通過不代表電路已通過工程驗證。
