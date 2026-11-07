---
name: pcb-local-ai
description: Assist KiCad PCB work using an optional local model or GPT conversation handoff, with explicit design checks.
---

# 本地 PCB AI 分工

歷史 SS9012 專案使用者已核定 `<project_root>/5VCE電路` 為SS9012專案唯一保留基準，要求捨棄RevA與RevB。後續從此版修改或開啟，不能回退到舊版。核定指設計版本選擇，不代表已完成實測或板廠製造核准。

目前先處理 KiCad，使用者已明確將 AD18 暫緩；不尋找 AD18 路徑或實作其控制器，除非使用者之後要求。依選定模式工作：local 使用 `http://127.0.0.1:8686/v1`，抉擇交目前 GPT 對話；gpt 不需本地模型，一般工作與抉擇均由目前 GPT 對話承接。

- 本地模型：資料整理、功能分組、依既定規則提出布局候選、程式草稿、檢查報告整理。
- Python／EDA 工具：精確計算、讀寫、布局評分、執行經驗證的操作與 ERC／DRC。
- GPT：方案取捨、互相衝突的規則、不可靠的元件或腳位資訊。只提供必要背景及選項，將決策交回本地模型。
- local 模式失敗就回報，不自動改用 GPT；使用者可明確切換 gpt。兩種模式均不由腳本呼叫雲端 API。

## 選擇有／無本地模型

第一次使用或使用者要求切換時，先確認模式。命令列提供互動選單：

```powershell
python scripts/local_worker.py configure
```

輸入 `1` 選有本地模型（local），輸入 `2` 選無本地模型（gpt）。選擇寫入 config.json 的 routine_work_provider，不寫死自動路徑。未選擇前維持原本 local 模式，不能因服務失敗自行切換。

也可直接設定或只對單次命令切換：

```powershell
python scripts/local_worker.py configure --provider gpt
python scripts/local_worker.py doctor --provider gpt
python scripts/local_worker.py work --provider gpt --role theory --task-file 任務.txt --output 交接.json
```

無本地模型模式：不連線本地服務、不需要模型檔或 API key；work 輸出 needs_gpt_work，包含完整 prompt、角色、規則與任務，退出碼 3 表示等待對話處理，不代表任務完成。使用者將 JSON 的 prompt 內容貼到 GPT 對話，或由目前已讀取本技能的協調者讀取交接檔並繼續處理。腳本不會自動傳送對話或呼叫雲端 API。doctor 在此模式只確認交接模式與工具路徑，不測推論。

目前 GPT 協調者承接時，保留相同工程驗證門檻；可用工具另行執行搜尋、計算與 EDA 操作，缺工具則回報限制，不把交接檔當作已完成設計。decision 命令仍為退出碼 3，決策可加入後續任務，不限使用本地模式。

## 使用

使用者要求完成後自動開啟：此專案每次修改並通過必要檢查、交付到指定資料夾後，開啟最新版本的KiCad專案及PCB編輯器，確認路徑與畫面。不要只留下檔案連結，也不要開舊版。若有未儲存的使用者修改，不自動捨棄。此項由協調者使用桌面工具執行，設定旗標本身不是已實作的背景自動排程。

以下路徑相對於本 Skill 目錄：

```powershell
python scripts/local_worker.py paths
python scripts/local_worker.py doctor
python scripts/local_worker.py work --task-file 任務.txt --output 結果.json
python scripts/local_worker.py work --role general --task-file 雜事.txt --output 通用結果.json
python scripts/local_worker.py decision --task-file 待抉擇.txt --output 抉擇.json
```

local 模式的 `work` 將任務文字送給本地模型；gpt 模式只產生完整交接內容；加入所需元件／網路資料、規則和既有決策，不把二進位專案、圖片或整個專案當文字送入。模型輸出只是待驗證草稿，不能直接 eval、exec 或當作 shell 命令執行。

`decision` 只產生交接檔並以退出碼 3 結束，不呼叫任何 AI。由目前 GPT 對話處理抉擇，再將結果加入下一個本地任務。退出碼 1 是錯誤，0 是成功。

## 五個本地角色

`--role parts` 是①零件助理；`schematic` 是②原理圖助理；`layout` 是③PCB布局助理；`general` 是④通用助理，亦為預設角色；`theory` 是⑤獨立理論檢查助理。五者共用本地模型，但每次請求只加入所選角色指令，不共享其他角色對話。

使用者輸入要做的電路時，先由理論助理列出需要的原廠資料、設計條件與理論來源；工具搜尋資料，零件助理核對元件，再由原理圖助理設計。完成後將使用者原始需求、Datasheet證據、實際元件值及匯出網路清單交理論助理獨立複查，不用設計助理的結論當證據。

理論檢查包含KCL/KVL、電流回路、腳位/極性、偏壓與工作區、額定與功耗、輸入輸出分離、共地或隔離條件、阻抗、耦合、負載、增益/頻寬及失真。缺證據或有功能錯誤時退回補資料/修正，再進PCB階段；模型PASS本身不等於工程驗證。搜尋、精確計算、模擬與ERC/DRC由實際工具補足。使用者已要求這些資料應由流程主動查找，不等使用者指出錯誤才補查。

通用助理承接檔案整理、格式轉換、索引維護、報告彙整、工作紀錄、錯誤資料與其他未分類工作。遇專業工作以 `HANDOFF` 提出轉交目標與必要背景，遇抉擇用 `NEEDS_DECISION` 交 GPT。這兩種標記目前由調用者處理，尚無自動角色調度或工具執行迴圈。

## 設計規則門檻

可重用門檻存於 `rules/pcb_requirements.json`。呼叫零件、原理圖、PCB、理論角色時，程式會把這份規則加入本地模型的指令；實際工具證據與是否放行仍由調用者檢查，尚不是自動工具排程器。

PCB助理必須查核並記錄適用的原廠封裝尺寸、板廠製程能力、電流/銅厚/溫升/壓降、銅間距、孔徑/環寬、板邊/元件courtyard、回流與功能區、絲印及製造層。參考IPC-2221通用設計與IPC-2152載流範圍，但不能把未取得全文、未核對板廠或未實測的設計宣稱為全面符合IPC。45度是本使用者指定的設計要求，不假稱所有業界電路都強制如此。

原理圖的電子電路學驗證和PCB製造規則是兩個獨立門檻；理論、ERC、DRC、原理圖/PCB一致性、幾何/線寬/層數/板框檢查都需留存實際結果。無法通過的項目列為FAIL或待確認，不以模型自述跳過。

第五個理論助理在SS9012首次獨立審閱曾犯PNP基流方向及耦合後DC錯誤。已用有符號KCL殘差與電容DC開路/負載回路驗證攔下，保留錯誤及更正紀錄。後續不得把「另一個AI同意」當成正確證明；必須配合數值或模擬工具。

此SS9012專案最新要求：40x40mm，單面B.Cu銅箔、無過孔；未經使用者接受不自行加入跳線。零件和courtyard在板框內。KiCad偶數虛擬銅層限制需說明，實際製造只輸出有銅的B.Cu；F.Cu不能有實際銅圖形。插件焊盤的邏輯層集合可能含F.Cu，須移除未接層焊盤並以FlashLayer及空白F.Cu Gerber驗證沒有正面銅環，不能只看層名稱就通過。

## 使用者元件庫

元件庫根目錄由 `component_library_root` 解析，預設為目前使用者家目錄下的 `Datasheet`。自建／下載資料集中存放，內建庫保留安裝原位並統一索引，不能自行搬移內建庫。

- `Datasheets`：規格書；`KiCad/symbols`：符號；`KiCad/footprints`：封裝；`KiCad/3dmodels`：3D 模型。
- `staging`：尚未驗證的下載或 AI 草稿，不直接加入已使用的元件庫。
- `index/library-index.json`：內建與個人符號／封裝的共同搜尋索引；新增／更新庫後需重建。索引不代表元件已通過驗證。
- `UserParts` 個人符號庫及封裝庫已加入 KiCad 10.0 全域清單，已包含 SS9012 專用符號及展腳封裝；其他新庫仍須註冊。
- 內建庫位於自動偵測或手動指定的 `builtin_library_root` 下的 `symbols`、`footprints`、`3dmodels`。`template` 內的庫表是清單，不是所有元件內容。
- 新電腦以實際 KiCad 庫清單和共同索引確認啟用狀態。

零件助理先查共同索引與本地 Datasheet，缺少所需項目才上網。分清規格書與可直接使用的 EDA 庫，不以檔名相近判定完整料號或封裝相符。精確核對腳位與封裝後才將草稿轉入個人庫。KiCad 全域清單修改前，將備份存於 `<component_library_root>/index/backups`。

## 環境與實作狀態

專案根目錄預設為目前使用者家目錄下的 `PCB-Projects`，每個電路使用獨立子資料夾；可在 `config.json` 的 `project_root` 覆寫。開發工具可放工作區，但交付的 KiCad 專案放指定專案根目錄。

`config.json` 使用可攜式設定，路徑在執行時自動解析。`doctor` 檢查本地服務與工具存在性；不代表已驗證 EDA 操作。

已有本地文字角色、抉擇交接、環境與元件庫索引，以及針對 SS9012 CE 示範的建檔、布局、走線及原生檢查程式。通用 AD18／KiCad 轉接器與角色自動調度仍未完成，不能把單一示範說成完整自動化。

## 使用者指定的 PCB 驗收要求

走線以 45° 轉角為要求，不能因原生 DRC 通過就接受直角自動路由。另驗證所有線段方向、焊盤外連續轉彎；焊盤本體及 T 接點分開記錄。

各網路線寬依工作電流／明示裕量、銅厚、溫升、線長、容許壓降與製程下限計算，將採用值寫進 PCB、網路類別及可檢查規則。不能用電晶體絕對最大電流當電路耗流，也不能把所有網路固定同寬卻不提供依據。歷史 IPC-2221 擬合與 IPC-2152 熱驗證需明確區分。

SS9012核定RevC採用使用者確認的外層35um、溫升10°C、最小線寬0.25mm、間距0.20mm。電源／地各以100mA連續裕量及壓降選電源0.55mm、地0.60mm，訊號與偏壓0.25mm；這些是此專案的假設，不能無條件套用到其他電路。

端子要求：電源輸入 J1(+5V/GND)、訊號輸入 J2(INPUT/GND)、訊號輸出 J3(OUTPUT/GND)三組獨立；只有地共用。理論與實際網路都需核對，不能把訊號 OUT 與 INPUT、電源、集極直流網或地混接。此 CE 輸出由集極經 C2 引出，開路時 C2 外側 DC 浮動，需明示負載條件。

目前先驗證 KiCad 讀寫與 DRC，元件／腳位／網路／規則／布局資料保留未來擴充空間。實作時查核實際安裝及版本 API。原始設計保留，修改輸出到副本；模型敘述不能作為檢查通過證據。

目前本地服務只宣告文字輸入；圖片／PDF 電路辨識仍須另行確認視覺模型或辨識工具。

## 跨電腦自動設定

複製整個技能資料夾。腳本需要 Python 3；實際 EDA 作業需要 KiCad；只有 local 模式需要本地 OpenAI 相容文字模型服務。程式不負責安裝工具或下載模型。

先執行 `python scripts/local_worker.py paths`，離線顯示本機解析結果，不建立資料夾、不連線、不改寫設定。選擇模式後執行 `doctor`；只有 local 模式需要先啟動本地服務。

- `null` 路徑會在每次執行時依目前使用者與環境自動填入。保持 null 才能跨帳號使用。
- `project_root` 預設 `~/PCB-Projects`；`component_library_root` 預設 `~/Datasheet`；索引、符號、封裝等由根目錄衍生。目錄不會自動建立，需在實際交付或建庫時建立並檢查權限。
- KiCad 優先採用明確設定，再查 PATH，其次查 ProgramFiles/KiCad 與 LOCALAPPDATA/Programs/KiCad，選版本號最高的 CLI。找不到就保持 null；非標準安裝位置請手動指定 `kicad_cli`。內建庫由該 CLI 安裝位置推導，仍須確認存在。
- 路徑可用 `~`、作業系統環境變數或相對路徑；相對路徑以設定檔所在目錄為基準。使用 JSON 字串時，Windows 反斜線須寫成 `\\`，也可使用 `/`。
- `model: null` 使用服務 `/models` 列出的唯一模型；零個或多個模型就停止，需設定正確模型 ID。模型 ID 不當作本機檔案路徑解析。
- `base_url` 預設 `http://127.0.0.1:8686/v1`，其他電腦的服務埠不同時須修改；仍僅允許本機端點。
- 發布設定不包含舊使用者的作用中專案或核定狀態。`active_project`、`active_pcb`、版本及 accepted_projects 由該電腦實際專案填寫，不自動猜選電路。前文 SS9012 規格僅適用該歷史電路，不代表新使用者核定。
- 自動解析不會搬移舊檔案、註冊庫或開啟 KiCad；設定旗標仍由外部協調者執行。
