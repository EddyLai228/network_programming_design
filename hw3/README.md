```bash
# 清理舊資料
cd hw3
make clean

# 啟動 Server（保持運行）
make server
```

**驗證點：**
- ✅ Developer Server 啟動在 8001
- ✅ Lobby Server 啟動在 8002
- ✅ 無錯誤訊息

### 2. 準備測試帳號

| 角色 | 用戶名 | 密碼 |
|------|--------|------|
| 開發者 | `dev1` | `dev123` |
| 玩家 1 | `player1` | `pass123` |
| 玩家 2 | `player2` | `pass123` |
| 玩家 3 | `player3` | `pass123` |

---

## 📊 Part 1: 系統功能完整度（55 分）

### D1: 開發者上架新遊戲（10 分）

**測試步驟：**

```bash
# 開啟 Developer Client
make developer HOST=linux4.cs.nycu.edu.tw
```

**操作流程：**

1. **註冊帳號**
   ```
   選擇: 2 (註冊)
   用戶名: dev1
   密碼: dev123
   ```
   **驗證點：**
   - ✅ 顯示「註冊成功」
   - ✅ 無錯誤訊息

2. **登入**
   ```
   選擇: 1 (登入)
   用戶名: dev1
   密碼: dev123
   ```
   **驗證點：**
   - ✅ 顯示「登入成功」
   - ✅ 進入開發者主選單

3. **上架 TicTacToe（CLI 雙人）**
   ```
   選擇: 2 (上架新遊戲)
   
   遊戲名稱: TicTacToe
   簡介: Classic tic-tac-toe game
   介面類型: 1 (CLI)
   遊戲模式: 2 (多人)
   玩家數: 2
   版本: 1.0.0
   選擇遊戲目錄: 5 (tictactoe_cli)
   
   # ✓ 系統會自動從 config.json 讀取啟動指令，無需手動輸入
   ```
   **驗證點：**
   - ✅ 顯示「上架成功」
   - ✅ 遊戲 ID 為 `dev1_TicTacToe`
   - ✅ 上傳進度顯示正常

4. **上架 TicTacToe（GUI 雙人）**
   ```
   選擇: 2 (上架新遊戲)
   
   遊戲名稱: TicTacToe_GUI
   簡介: Two-player GUI
   介面類型: 2 (GUI)
   遊戲模式: 2 (多人)
   玩家數: 2
   版本: 1.0.0
   選擇遊戲目錄: 2 (tictactoe_gui_two)
   
   # ✓ 自動讀取啟動指令
   ```
   **驗證點：**
   - ✅ 顯示「上架成功」
   - ✅ 遊戲 ID 為 `dev1_TicTacToe_GUI`

5. **上架 Blackjack（CLI 多人）**
   ```
   選擇: 2 (上架新遊戲)
   
   遊戲名稱: Blackjack
   簡介: 21點撲克牌遊戲，支持3人對戰莊家
   介面類型: 1 (CLI)
   遊戲模式: 2 (多人)
   玩家數: 3
   版本: 1.0.0
   選擇遊戲目錄: 4 (blackjack)
   
   # ✓ 自動讀取啟動指令
   ```
   **驗證點：**
   - ✅ 顯示「上架成功」
   - ✅ 遊戲 ID 為 `dev1_Blackjack`

5. **上架 snake**
   ```
   選擇: 2 (上架新遊戲)
   
   遊戲名稱: snake
   簡介: snake
   介面類型: 2 (GUI)
   遊戲模式: 1 (單人)
   玩家數: 1
   版本: 1.0.0
   選擇遊戲目錄: 6 (snake)
   
   # ✓ 自動讀取啟動指令
   ```
   **驗證點：**
   - ✅ 顯示「上架成功」
   - ✅ 遊戲 ID 為 `dev1_Blackjack`

6. **確認上架結果**
   ```
   選擇: 1 (查看我的遊戲)
   ```
   **驗證點：**
   - ✅ 顯示 3 款遊戲
   - ✅ 版本都是 1.0.0
   - ✅ 狀態都是「已上架」

---

### D2: 更新已上架遊戲版本（10 分）

**測試步驟：**

1. **更新 TicTacToe 版本**
   ```
   選擇: 3 (更新遊戲)
   選擇遊戲: (snake)
   新版本號: 1.1.0
   更新說明：選填
   遊戲目錄：3
   ```
   **驗證點：**
   - ✅ 顯示「更新成功」
   - ✅ 版本號從 1.0.0 變更為 1.1.0

2. **確認版本更新**
   ```
   選擇: 1 (查看我的遊戲)
   ```
   **驗證點：**
   - ✅ TicTacToe 版本為 1.1.0
   - ✅ 其他遊戲版本不變

---

### D3: 下架遊戲（5 分）

**測試步驟：**

1. **下架 Snake 遊戲**
   ```
   選擇: 4 (下架遊戲)
   選擇遊戲: 2 (Snake)
   確認: yes
   ```
   **驗證點：**
   - ✅ 顯示「下架成功」
   - ✅ 提示玩家無法再下載

2. **確認下架結果**
   ```
   選擇: 1 (查看我的遊戲)
   ```
   **驗證點：**
   - ✅ Snake 狀態變更為「已下架」
   - ✅ 其他遊戲不受影響

---

### P1: 玩家瀏覽遊戲商城（5 分）

**測試步驟：**

```bash
# 開啟 Player Client
make player HOST=linux4.cs.nycu.edu.tw
```

**操作流程：**

1. **註冊並登入**
   ```
   選擇: 2 (註冊)
   用戶名: player1
   密碼: pass123
   
   選擇: 1 (登入)
   用戶名: player1
   密碼: pass123
   ```

2. **瀏覽所有遊戲**
   ```
   選擇: 1 (瀏覽遊戲商城)
   選擇: 1 (瀏覽所有遊戲)
   ```

3. **查看遊戲詳情**
   ```
   選擇: 1 (瀏覽遊戲商城)
   選擇: 2 (查看遊戲詳情)
   選擇遊戲: TicTacToe
   ```
   **驗證點：**
   - ✅ 顯示完整資訊（名稱、版本、作者、簡介）
   - ✅ 顯示評分與評論數
   - ✅ 介面清楚易讀

---

### P2: 下載, 更新遊戲（10 分）

### P3: 建立房間並啟動遊戲（10 分）

**測試步驟：**

#### 1. Player 1 建立房間

```
選擇: 5 (遊戲房間)
選擇: 2 (建立房間)
選擇遊戲: TicTacToe
房間名稱: Test Room
```
**驗證點：**
- ✅ 顯示「房間建立成功」
- ✅ 房間 ID 顯示

#### 2. Player 2 加入房間

*（開啟第二個 Player Client）*

```bash
make player
```

```
註冊並登入 player2
選擇: 5 (遊戲房間)
選擇: 3 (加入房間)
選擇房間: Test Room
```
**驗證點：**
- ✅ Player 1 收到「player2 加入房間」通知
- ✅ 房間人數從 1/2 變更為 2/2

#### 3. Player 1 開始遊戲

```
選擇: 5 (開始遊戲)
```
**驗證點：**
- ✅ **自動開啟 Player 1 遊戲視窗**
- ✅ Player 2 收到遊戲開始通知
- ✅ **1 秒後自動開啟 Player 2 遊戲視窗**
- ✅ 兩個視窗都連接成功

#### 4. 進行遊戲

**Player 1 操作（X）：**
```
輸入座標: 0 0
```

**Player 2 操作（O）：**
```
輸入座標: 1 1
```

**繼續對戰直到遊戲結束**

**驗證點：**
- ✅ 棋盤狀態同步更新
- ✅ 輪流機制正確
- ✅ 遊戲結束後顯示結果

#### 5. 遊戲結束處理

**驗證點：**
- ✅ 兩個玩家都看到遊戲結果
- ✅ 遊戲視窗自動關閉或提示結束
- ✅ 回到大廳選單
- ✅ 房間狀態重置為「等待中」
- ✅ 可以再次開始新一局

**評分標準（10 分）：**
- 房間建立/加入：2 分
- 遊戲自動啟動：3 分
- 遊戲對戰流程：3 分
- 結束與重置：2 分

---

### P4: 評分與留言（5 分）

**測試步驟：**

1. **評分遊戲**
   ```
   選擇: 1 (瀏覽遊戲商城)
   選擇: 2 (查看遊戲詳情)
   選擇遊戲: TicTacToe
   是否評分: yes
   評分: 5
   評論: Great game! Very fun!
   ```
   **驗證點：**
   - ✅ 顯示「評分成功」
   - ✅ 評分立即反映在遊戲詳情

2. **查看評論**
   ```
   選擇: 1 (瀏覽遊戲商城)
   選擇: 2 (查看遊戲詳情)
   選擇遊戲: TicTacToe
   ```
   **驗證點：**
   - ✅ 顯示平均評分
   - ✅ 顯示評論列表
   - ✅ 包含用戶名、評分、評論內容

3. **測試限制**
   
   *（嘗試對未遊玩的遊戲評分）*
   
   **驗證點：**
   - ✅ 顯示錯誤訊息「尚未遊玩此遊戲」
   - ✅ 不允許評分

**評分標準（5 分）：**
- 成功評分：2 分
- 評論顯示：2 分
- 權限檢查：1 分

---

## 🎮 Part 2: 遊戲實作程度（15 分）

### 關卡 A: CLI 雙人遊戲（5 分）

**測試遊戲：TicTacToe**

**驗證清單：**

1. **✅ 支援 2 位玩家對戰**
   - Player 1 和 Player 2 都能連接
   - 兩個客戶端都能看到遊戲狀態

2. **✅ 完整遊戲流程**
   - 開始遊戲：遊戲視窗正常開啟
   - 進行對戰：
     - 輪流下棋
     - 棋盤狀態即時更新
     - 輸入驗證（不能下在已有棋子的位置）
   - 結束並顯示結果：
     - 顯示勝負或平局
     - 顯示最終棋盤
     - 正常退出

3. **✅ 穩定性**
   - 無當機
   - 無卡死
   - 連線穩定

**評分標準：**
- 完整流程（5 分）
- 部分功能（0-3 分）

---

### 關卡 B: GUI 介面（+5 分）

**測試遊戲：TicTacToe**

**驗證清單：**

1. **✅ 基本圖形介面**
   - 有視窗（Pygame）
   - 顯示遊戲畫面
   - 視覺元素清楚

2. **✅ GUI 操作**
   - 不需要輸入指令
   - 操作即時反應

3. **✅ 狀態更新**
   - 蛇的移動即時顯示
   - 分數即時更新
   - 遊戲結束顯示結果畫面

---

### 關卡 C: 多人同局遊玩（+5 分）

**測試遊戲：Blackjack（21點）**

**驗證清單：**

1. **✅ 支援 3+ 玩家**
   - 3 位玩家同時遊玩
   - 人數檢查機制

2. **✅ 連線與狀態更新**
   - 所有玩家看到相同遊戲狀態
   - 輪流機制正確
   - 同步邏輯合理

3. **✅ 實際操作驗證**
   - 助教可以操作 3 個帳號
   - 跑完一局完整遊戲
   - 無錯誤或卡頓

**測試流程：**

#### 1. 準備 3 位玩家

**Terminal 1-3：分別啟動 3 個 Player Client**

```bash
# Terminal 1
make player
# 登入 player1

# Terminal 2
make player
# 登入 player2

# Terminal 3
make player
# 登入 player3
```

#### 2. 建立 Blackjack 房間

**Player 1：**
```
選擇: 5 (遊戲房間)
選擇: 2 (建立房間)
選擇遊戲: Blackjack
房間名稱: 21點房
```

**Player 2 & 3：**
```
選擇: 5 (遊戲房間)
選擇: 3 (加入房間)
選擇房間: 21點房
```

**驗證點：**
- ✅ 房間人數：3/6

#### 3. 開始遊戲

**Player 1：**
```
選擇: 5 (開始遊戲)
```

**驗證點：**
- ✅ 3 個視窗都自動開啟
- ✅ 顯示「等待玩家加入...」
- ✅ 達到 3 人後 5 秒自動開始

#### 4. 進行遊戲

**下注階段：**
```
Player 1: 100
Player 2: 50
Player 3: 200
```

**發牌：**
- ✅ 每位玩家看到自己的 2 張牌
- ✅ 看到莊家的 1 張明牌

**行動階段（輪流）：**

**Player 1：**
```
選擇: h (要牌)
總點數: 18
選擇: s (停牌)
```

**Player 2：**
```
選擇: h (要牌)
總點數: 22 (爆牌)
```

**Player 3：**
```
選擇: d (加倍)
總點數: 20
```

**莊家補牌：**
- ✅ 自動補牌到 ≥17

**結算：**
- ✅ 顯示所有玩家結果
- ✅ 顯示剩餘籌碼
- ✅ 自動開始下一局

**驗證點：**
- ✅ 3 位玩家都能正常操作
- ✅ 遊戲邏輯正確（點數計算、勝負判定）
- ✅ 輪流機制流暢
- ✅ 跑完完整一局

**評分標準：**
- 完整多人功能（5 分）
- 部分功能（0-3 分）

---

## 🏗️ Part 3: 系統架構與正確性（5 分）

### 測試項目

#### 1. 三種角色模組切分（2 分）

**驗證清單：**

```bash
# 檢查目錄結構
ls -la hw3/
```

**驗證點：**
- ✅ `server/` - Server 模組
  - `lobby_server.py` - 玩家服務
  - `developer_server.py` - 開發者服務
  - `data/` - 資料儲存
- ✅ `developer/` - Developer 模組
  - `developer_client.py` - 開發者客戶端
  - `games/` - 遊戲原始碼
- ✅ `player/` - Player 模組
  - `lobby_client.py` - 玩家客戶端
  - `downloads/` - 下載的遊戲

**通訊檢查：**
- ✅ Developer ↔ Developer Server (8001)
- ✅ Player ↔ Lobby Server (8002)
- ✅ Player ↔ Game Server (動態端口)

#### 2. 版本管理與檔案來源（2 分）

**驗證清單：**

1. **Developer 端遊戲原始碼**
   ```bash
   ls developer/games/tictactoe_cli/
   ```
   **驗證點：**
   - ✅ 包含 `game.py`, `config.json`
   - ✅ 這是開發者本地版本

2. **Server 上架版本**
   ```bash
   ls server/data/games/dev1_TicTacToe/
   ```
   **驗證點：**
   - ✅ 上架後複製到 Server
   - ✅ 版本號記錄在 `games.json`

3. **Player 下載版本**
   ```bash
   ls player/downloads/player1/dev1_TicTacToe/
   ```
   **驗證點：**
   - ✅ 從 Server 下載
   - ✅ 版本號記錄在本地 `config.json`

4. **版本一致性**
   ```bash
   # 比較版本號
   cat server/data/games.json | grep TicTacToe
   cat player/downloads/player1/dev1_TicTacToe/config.json
   ```
   **驗證點：**
   - ✅ 版本號一致
   - ✅ 更新機制正確

#### 3. 資料持久化（1 分）

**測試步驟：**

1. **建立測試資料**
   - 開發者上架遊戲
   - 玩家下載遊戲
   - 玩家評分

2. **重啟 Server**
   ```bash
   # 停止 Server (Ctrl+C)
   # 重新啟動
   make server
   ```

3. **驗證資料保留**
   
   **Developer Client：**
   ```
   選擇: 1 (查看我的遊戲)
   ```
   **驗證點：**
   - ✅ 上架的遊戲仍在
   - ✅ 版本號正確
   
   **Player Client：**
   ```
   選擇: 1 (瀏覽遊戲商城)
   選擇: 2 (查看遊戲詳情)
   ```
   **驗證點：**
   - ✅ 遊戲列表正確
   - ✅ 評分與評論保留
   - ✅ 玩家遊玩歷史保留

**評分標準（5 分）：**
- 模組切分清楚：2 分
- 版本管理合理：2 分
- 資料持久化：1 分

---

## 🎨 Part 4: 使用者體驗與介面設計（5 分）

### 測試項目

#### 1. Menu 結構清楚（2 分）

**Developer Menu 驗證：**

```
=== 開發者主選單 ===
1. 查看我的遊戲
2. 上架新遊戲
3. 更新遊戲
4. 下架遊戲
5. 登出
```

**驗證點：**
- ✅ 選項清楚，不超過 7 個
- ✅ 層級合理（不會全塞在一層）
- ✅ 數字對應邏輯

**Player Menu 驗證：**

```
=== 玩家主選單 ===
1. 瀏覽遊戲商城
2. 已下載的遊戲
3. 下載遊戲
4. 檢查遊戲更新
5. 遊戲房間
6. 登出
```

**驗證點：**
- ✅ 功能分類清楚
- ✅ 操作直覺
- ✅ 返回上一層機制

#### 2. Demo 流程直覺（2 分）

**測試方法：**

請一位不熟悉系統的人，僅依照 QUICKSTART.md，嘗試完成：

1. 啟動 Server
2. 開發者上架遊戲
3. 玩家下載並遊玩
4. 評分

**驗證點：**
- ✅ 不需要額外解釋
- ✅ 步驟清楚
- ✅ 5 分鐘內可完成基本流程

#### 3. 錯誤訊息清楚（1 分）

**測試場景：**

1. **登入失敗**
   ```
   輸入錯誤密碼
   ```
   **驗證點：**
   - ✅ 顯示「密碼錯誤」而非「Error 401」

2. **連線失敗**
   ```
   Server 未啟動時連接
   ```
   **驗證點：**
   - ✅ 顯示「無法連接到伺服器」而非「Connection refused」

3. **版本衝突**
   ```
   嘗試下載已下架的遊戲
   ```
   **驗證點：**
   - ✅ 顯示「遊戲已下架，無法下載」

4. **權限錯誤**
   ```
   未遊玩遊戲就評分
   ```
   **驗證點：**
   - ✅ 顯示「尚未遊玩此遊戲」

**評分標準（5 分）：**
- Menu 結構：2 分
- Demo 流程：2 分
- 錯誤訊息：1 分

---

## 💻 Part 5: 程式碼品質與文件（5 分）

### 測試項目

#### 1. 程式碼結構（3 分）

**檢查項目：**

1. **命名規範**
   ```python
   # 檢查 lobby_server.py
   cat server/lobby_server.py | grep "def "
   ```
   **驗證點：**
   - ✅ 函數名稱有意義（如 `handle_login`, `create_room`）
   - ✅ 變數名稱清楚（如 `username`, `game_id`）

2. **模組化**
   ```python
   # 檢查是否有重複代碼
   ```
   **驗證點：**
   - ✅ 功能分離（Protocol, Database, Server）
   - ✅ 可讀性高
   - ✅ 不是 Spaghetti Code

3. **註解與文檔**
   ```python
   # 檢查關鍵函數註解
   ```
   **驗證點：**
   - ✅ 關鍵函數有 docstring
   - ✅ 複雜邏輯有說明

#### 2. README 文件（2 分）

**檢查清單：**

```bash
cat README.md
cat QUICKSTART.md
```

**驗證點：**

1. **環境需求說明**
   - ✅ Python 版本
   - ✅ 依賴套件（pygame）
   - ✅ 安裝指令

2. **啟動步驟**
   - ✅ Server 啟動方式
   - ✅ Developer 使用方式
   - ✅ Player 使用方式

3. **基本操作**
   - ✅ 上架遊戲流程
   - ✅ 下載遊玩流程
   - ✅ 評分流程

4. **故障排除**
   - ✅ 常見錯誤解決方法
   - ✅ 端口衝突處理

**評分標準（5 分）：**
- 程式碼結構：3 分
- README 文件：2 分

---

## 🎤 Part 6: 口頭問答準備（15 分）

### 問題 1: 系統架構說明（5 分）

**可能問題：**
> 請說明你們的系統架構，Server / Developer / Player 如何溝通？

**準備答案架構：**

```
1. 三層架構：
   - Server 層（8001/8002）
   - Developer 層（開發者客戶端）
   - Player 層（玩家客戶端）

2. 通訊方式：
   - Developer ↔ Developer Server (8001)
     - TCP Socket
     - JSON 格式資料
     - 檔案傳輸使用分塊傳輸
   
   - Player ↔ Lobby Server (8002)
     - TCP Socket
     - JSON 格式資料
     - 長連接監聽房間更新
   
   - Player ↔ Game Server (動態端口)
     - 由 Lobby Server 啟動
     - 端口動態分配（15000+）
     - 遊戲結束自動清理

3. 資料流：
   - 上架：Developer → Server (games 目錄)
   - 下載：Server → Player (downloads 目錄)
   - 遊玩：Player → Game Server (記錄歷史)
   - 評分：Player → Server (reviews.json)

4. 資料儲存：
   - games.json - 遊戲資訊
   - players.json - 玩家帳號
   - rooms.json - 房間狀態
   - reviews.json - 評分評論
   - 所有資料使用檔案鎖定（threading.Lock）
```

**圖示準備：**
```
┌─────────────────────────────────────────────┐
│              Server 層 (遠程)                │
│  ┌──────────────┐      ┌─────────────────┐ │
│  │ Developer    │      │ Lobby Server    │ │
│  │ Server       │      │ + Game Servers  │ │
│  │ (8001)       │      │ (8002, 15000+)  │ │
│  └──────────────┘      └─────────────────┘ │
│         ↑                       ↑           │
└─────────┼───────────────────────┼───────────┘
          │                       │
    ┌─────┴────────┐      ┌──────┴──────────┐
    │ Developer    │      │ Player Client   │
    │ Client       │      │ (多個玩家)      │
    │ (本地)       │      │ (本地)          │
    └──────────────┘      └─────────────────┘
```

---

### 問題 2: 功能擴展（5 分）

**可能問題：**
> 如果要新增 VR 遊戲類型，你會怎麼改？

**準備答案：**

```python
# 1. 修改 developer_client.py
def upload_game(self):
    print("請選擇介面類型:")
    print("1. CLI")
    print("2. GUI")
    print("3. VR")  # 新增
    choice = input("選擇: ")
    
    interface_map = {
        '1': 'cli',
        '2': 'gui',
        '3': 'vr'  # 新增
    }

# 2. 更新 games.json schema
{
    "game_id": "dev1_VRGame",
    "interface": "vr",  # 新類型
    "vr_platform": "Quest",  # 新欄位
    ...
}

# 3. Player 端檢查
def download_game(self):
    if game['interface'] == 'vr':
        if not self.check_vr_support():
            print("您的設備不支援 VR 遊戲")
            return
```

**可能問題：**
> 如果要新增遊戲標籤（tags）功能，你會怎麼改？

**準備答案：**

```python
# 1. 修改上架流程（developer_client.py）
tags = input("遊戲標籤（逗號分隔，例如: action,multiplayer）: ")
game_info['tags'] = [t.strip() for t in tags.split(',')]

# 2. 更新搜尋功能（lobby_client.py）
def search_by_tag(self, tag):
    games = self.get_all_games()
    return [g for g in games if tag in g.get('tags', [])]

# 3. 更新顯示
def display_game_details(self, game):
    print(f"標籤: {', '.join(game.get('tags', []))}")
```

---

### 問題 3: Bug 處理（5 分）

**可能問題：**
> 如果 Lobby Server 掛掉，正在進行的遊戲會怎樣？

**準備答案：**

```
1. 遊戲不受影響：
   - Game Server 是獨立進程
   - 由 Lobby Server 啟動，但之後獨立運行
   - 玩家與 Game Server 直接通訊

2. 重啟後恢復：
   - 資料儲存在 JSON 檔案
   - Server 重啟後讀取資料
   - 房間狀態、玩家歷史都保留

3. 改進方案：
   - 心跳檢測（heartbeat）
   - 自動重連機制
   - 備份 Server（高可用性）
```

**可能問題：**
> 如果 Game Server 卡住不結束，怎麼辦？

**準備答案：**

```
現有機制：
1. 房主可手動「結束遊戲」
2. 端口監控自動檢測並重置
3. 超時機制（遊戲啟動 10 秒後才檢查）

程式碼位置：
# lobby_server.py
def _monitor_game_ports(self):
    # 每 5 秒檢查遊戲端口
    # 端口關閉時自動重置房間
    
def handle_end_game(self):
    # 終止遊戲服務器進程
    if room_id in self.game_servers:
        process = self.game_servers[room_id]
        process.terminate()
```

**可能問題：**
> 版本衝突怎麼處理？

**準備答案：**

```
1. 玩家下載時：
   - 檢查本地版本
   - 比對 Server 版本
   - 提示是否更新

2. 版本降級：
   - 不允許開發者降版本
   - 玩家可選擇不更新（但可能無法遊玩）

3. 遊戲啟動時：
   - 檢查版本相容性
   - 不相容時提示更新

程式碼：
# lobby_client.py
def check_updates(self):
    local_version = self.get_local_version(game_id)
    server_version = self.get_server_version(game_id)
    if server_version > local_version:
        print(f"有新版本 {server_version}")
```

---

### 現場修改題準備

**可能任務：**
> 現場新增一個功能：顯示遊戲下載次數

**準備步驟：**

```python
# 1. 修改 games.json schema
{
    "game_id": "...",
    "download_count": 0  # 新增
}

# 2. 下載時更新（lobby_server.py）
def handle_download_game(self, data, username):
    # ... 下載邏輯 ...
    
    # 更新下載次數
    game = self.db.get_game(game_id)
    game['download_count'] = game.get('download_count', 0) + 1
    self.db.update_game(game_id, game)

# 3. 顯示時輸出（lobby_client.py）
def display_game_details(self, game):
    print(f"下載次數: {game.get('download_count', 0)}")
```

**時間估計：5-10 分鐘**

---

## 📊 評分總結表

| 項目 | 配分 | 測試要點 | 檢查狀態 |
|------|------|----------|----------|
| **D1** | 10 | 成功上架 3 款遊戲 | ☐ |
| **D2** | 10 | 版本更新與驗證 | ☐ |
| **D3** | 5 | 下架遊戲 | ☐ |
| **P1** | 5 | 瀏覽遊戲商城 | ☐ |
| **P2** | 10 | 下載與更新 | ☐ |
| **P3** | 10 | 建立房間並遊玩 | ☐ |
| **P4** | 5 | 評分與留言 | ☐ |
| **關卡 A** | 5 | TicTacToe 完整流程 | ☐ |
| **關卡 B** | 5 | Snake GUI 功能 | ☐ |
| **關卡 C** | 5 | Blackjack 3+ 玩家 | ☐ |
| **架構** | 5 | 模組切分、版本管理、持久化 | ☐ |
| **體驗** | 5 | Menu、流程、錯誤訊息 | ☐ |
| **品質** | 5 | 程式碼、文件 | ☐ |
| **問答** | 15 | 架構說明、擴展、除錯 | ☐ |
| **總計** | **100** |  |  |

---

## 🎯 快速測試腳本

### 完整測試流程（30 分鐘）

```bash
# 1. 清理並啟動（2 分鐘）
make clean
make server

# 2. Developer 上架（5 分鐘）
make developer
# 註冊 dev1、上架 3 款遊戲

# 3. Player 下載（3 分鐘）
make player
# 註冊 player1、下載 TicTacToe & Blackjack

# 4. 雙人對戰（5 分鐘）
# Terminal 1: player1 建立房間
# Terminal 2: player2 加入房間
# 遊玩 TicTacToe

# 5. 多人對戰（10 分鐘）
# Terminal 1-3: 3 位玩家
# 遊玩 Blackjack

# 6. 評分與更新（5 分鐘）
# player1 評分
# dev1 更新版本
# player1 檢查更新
```

---

## 📝 Demo 當天檢查清單

**Demo 前（10 分鐘）：**
- ☐ `make clean` - 清理舊資料
- ☐ `make server` - 確認 Server 正常啟動
- ☐ 準備至少 4 個終端視窗
- ☐ 確認網路連線正常
- ☐ 檢查 pygame 已安裝

**Demo 中：**
- ☐ 按照評分順序展示功能
- ☐ 每個 Use Case 都要展示
- ☐ 三款遊戲都要運行
- ☐ 準備回答問題

**Demo 後：**
- ☐ `make clean` - 清理測試資料

---

## 🏆 加分項目（最多 20 分）

### 可能的加分方向

1. **額外功能（5-10 分）**
   - 聊天室
   - 好友系統
   - 排行榜
   - 遊戲錄影回放

2. **技術亮點（5-10 分）**
   - 使用資料庫（SQLite/PostgreSQL）
   - Web 介面（Flask/FastAPI）
   - 容器化部署（Docker）
   - 負載平衡

3. **使用者體驗（5 分）**
   - 精美 GUI
   - 音效與動畫
   - 教學模式
   - 無障礙設計

---

## 📞 聯絡資訊

如有問題請聯絡開發團隊。

**祝 Demo 順利！🎉**
