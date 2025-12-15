# 🎮 Game Store System - Demo 指南

完整的遊戲商城系統，支援開發者上架遊戲、玩家下載遊玩、多人房間、評分評論等功能。

## 📋 系統概述

### 功能特色
- ✅ **完整 Use Cases**：D1-D3（開發者）、P1-P4（玩家）
- ✅ **三款遊戲**：
  - **Tic-Tac-Toe** - CLI 雙人遊戲（關卡 A）
  - **Snake Battle** - Pygame GUI 雙人對戰（關卡 B）
  - **Blackjack** - CLI 3-6人多人遊戲（關卡 C）
- ✅ **自動化遊戲生命週期**：自動啟動、監控、結束、顯示結果
- ✅ **資料持久化**：Server 重啟後資料不遺失

### 系統架構
```
Server 層 (8001/8002) ← Developer 端 (上架遊戲)
                      ← Player 端 (下載/遊玩/評分)
                      → Game Servers (動態端口)
```

---

## 🚀 快速開始（總時長：20分鐘）

### Step 1: 啟動伺服器（1分鐘）

#### Terminal 1: 啟動 Servers
```bash
cd hw3
make server
```

**成功畫面：**
```
🚀 啟動 Game Store Servers...
  - Developer Server: http://localhost:8001
  - Lobby Server: http://localhost:8002

Lobby Server started on 0.0.0.0:8002
Developer Server started on 0.0.0.0:8001
```

保持此終端運行。

---

## Step 2: 開發者上架遊戲（5分鐘）

#### Terminal 2: Developer Client

```bash
cd hw3
make developer
```

### 📝 操作流程

**1. 註冊/登入**
- 選擇 `2` 註冊 → 用戶名: `dev1` / 密碼: `dev123`
- 選擇 `1` 登入 → 用戶名: `dev1` / 密碼: `dev123`

**2. 上架 TicTacToe（關卡 A：CLI 雙人）**

選擇 `2` 上架新遊戲：
```
遊戲名稱: TicTacToe
簡介: Classic tic-tac-toe game
介面類型: 1 (CLI)
遊戲模式: 2 (多人)
玩家數: 2
版本: 1.0.0
啟動指令: python game.py client --host localhost
選擇目錄: 1 (tictactoe)
```

**3. 上架 Snake Battle（關卡 B：GUI 雙人）**

選擇 `2` 上架新遊戲：
```
遊戲名稱: Snake Battle
簡介: Two-player snake battle game
介面類型: 2 (GUI)
遊戲模式: 2 (多人)
玩家數: 2
版本: 1.0.0
啟動指令: python game.py client --host localhost
選擇目錄: 2 (snakebattle)
```

**4. 上架 Blackjack（關卡 C：CLI 3-6人）**

選擇 `2` 上架新遊戲：
```
遊戲名稱: Blackjack
簡介: 21點撲克牌遊戲，支持3-6人對戰莊家
介面類型: 1 (CLI)
遊戲模式: 2 (多人)
玩家數: 6
版本: 1.0.0
啟動指令: python game.py client --host localhost
選擇目錄: 3 (blackjack)
```

**5. 確認上架**
- 選擇 `1` 查看我的遊戲 → 確認三款遊戲都已上架
玩家體驗（10分鐘）

### 📌 Demo 方案選擇

**方案 A：自動化遊戲（推薦，展示完整功能）**
- 使用 TicTacToe 或 Snake Battle
- 系統自動啟動遊戲、自動顯示結果
- 展示完整的自動化遊戲生命週期

**方案 B：多人遊戲（展示關卡 C）**
- 使用 Blackjack（3-6人）
- 展示多人同局遊玩、輪流機制

---

### 🎯 方案 A：自動化遊戲 Demo（推薦）

#### Terminal 3: Player 1
```bash
cd hw3
make player
```

**操作：**
1. 選擇 `2` 註冊 → `player1` / `pass123`
2. 選擇 `1` 登入 → `player1` / `pass123`
3. 選擇 `1` 瀏覽遊戲商城 → `1` 瀏覽所有遊戲 → 查看三款遊戲
4. 選擇 `3` 下載遊戲 → 選擇 `1` (TicTacToe) → 等待下載

#### Terminal 4: Player 2
```bash
cd hw3
make player
```

**操作：**
1. 選擇 `2` 註冊 → `player2` / `pass123`
2. 選擇 `1` 登入 → `player2` / `pass123`
3. 選擇 `1` 瀏覽遊戲商城 → `3` 下載遊戲 → 選擇 `1` (TicTacToe)

#### 創建房間並自動遊玩

**Player 1 操作：**
```
選擇 3 (遊戲房間)
選擇 2 (建立房間)
選擇遊戲: 1 (TicTacToe)
房間名稱: Demo Room
選擇 3 (加入房間)
選擇 1 (Demo Room)
選擇 5 (開始遊戲)
```

**✨ 自動化效果：**
- 🎮 Player 1 遊戲視窗自動開啟
- 🎮 Player 2 遊戲視窗自動開啟（1秒後）
- 🎯 兩人對戰完成後，結果自動顯示在大廳
- 📊 房間自動重置，可再次遊玩

**Player 2 操作：**
```
選擇 3 (遊戲房間)
選擇 3 (加入房間)
選擇 1 (Demo Room)
等待 Player 1 開始遊戲
```

#### 評分評論（展示 P4）

**任一玩家操作：**
```
選擇 1 (瀏覽遊戲商城)
選擇 2 (查看遊戲詳情)
選擇 1 (TicTacToe)
輸入 yes (評分)
評分: 5
評論: Great game!
```

---

### 🎲 方案 B：Blackjack 多人 Demo（展示關卡 C）

**需要 3-6 個玩家終端**

#### Terminal 3-5: 3 位玩家

每個終端執行：
```bash
cd hw3
make player
```

**每位玩家操作：**
1. 註冊/登入（player1/player2/player3）
2. 下載 Blackjack 遊戲
3. 加入同一房間

#### 開始 Blackjack 遊戲

**房主（Player 1）操作：**
```
選擇 3 (遊戲房間)
選擇 2 (建立房間)
選擇遊戲: Blackjack
房間名稱: 21點房
選擇 3 (加入房間)
選擇 5 (開始遊戲)
```

**其他玩家操作：**
```
選擇 3 (遊戲房間)
選擇 3 (加入房間)
選擇房間
等待房主開始
```

**🎮 遊戲流程：**
1. 等待玩家加入（3-6人，達3人後5秒自動開始）
2. **下注階段**：每位玩家輪流下注（$1-$1000）
3. **發牌**：每人2張，莊家2張（1張暗牌）
4. **玩家回合**：輪流選擇
   - `h` (要牌)
   - `s` (停牌)
   - `d` (加倍，僅前兩張牌時)
5. **莊家補牌**：自動補牌到≥17點
6. **結算**：顯示每位玩家結果和剩餘籌碼
7. **下一局**：自動開始（直到有人破產）

---

## 📊 展示完成的功能

### ✅ 開發者 Use Cases (D1-D3)
- **D1 (10分)**: 上架新遊戲 ✅
- **D2 (10分)**: 更新遊戲版本 ✅
- **D3 (5分)**: 下架遊戲 ✅

### ✅ 玩家 Use Cases (P1-P4)
- **P1 (5分)**: 瀏覽遊戲商城 ✅
- **P2 (10分)**: 下載/更新遊戲 ✅
- **P3 (10分)**: 創建房間並遊玩 ✅
- **P4 (5分)**: 評分與評論 ✅

### ✅ 遊戲實作 (15分)
- **關卡 A (5分)**: TicTacToe - CLI 雙人 ✅
- **關卡 B (5分)**: Snake Battle - GUI 雙人 ✅
- **關卡 C (5分)**: Blackjack - CLI 3-6人 ✅mo Features

現在你可以展示以下功能:

### Developer Features (D1-D3)
- ✅ D1: 上架新遊戲
- ✅ D2: 更新遊戲 (選擇「更新遊戲」，輸入新版本號)
- ✅ D3: 下架遊戲 (選擇「下架遊戲」)

### Player Features (P1-P4)
- ✅ P1: 瀏覽遊戲商城
- ✅ P2: 下載遊戲
- ✅ P3: 建立房間並遊玩
- ✅ P4: 評分與評論

---

## 🎯 口頭問答準備

### 系統架構說明

**三層架構：**
```
Server 層 (8001/8002)
  ├── developer_server.py - 處理開發者操作
  ├── lobby_server.py - 處理玩家操作
  └── data/ - JSON 資料儲存

Developer 層
  ├── developer_client.py - 開發者客戶端
  └── games/ - 遊戲原始碼

Player 層
  ├── lobby_client.py - 玩家客戶端
  └── downloads/ - 下載的遊戲
```

**通訊流程：**
- Developer → developer_server：上架/更新/下架
- Player → lobby_server：瀏覽/下載/房間/評分
- Player → game_server：遊玩遊戲（動態端口）

**資料持久化：**
- 所有資料儲存在 JSON 檔案（server/data/）
- 檔案鎖定機制（threading.Lock）
- Server 重啟後資料不遺失

### 功能擴展方案

**Q: 如何新增遊戲類型（例如 VR）？**

A: 修改 `developer_client.py` 的 `upload_game()` 函數：
```python
print("請選擇介面類型:")
print("1. CLI")
print("2. GUI")
print("3. VR")  # 新增
```

**Q: 如何新增資料欄位（例如遊戲標籤）？**

A: 在 `games.json` 中新增欄位：
```json
{
  "game_id": "dev1_GameName",
  "tags": ["action", "multiplayer"],  // 新增
  ...
}
```

### Bug 處理方案

**Q: Lobby Server 掛掉怎麼辦？**
- 正在進行的遊戲不受影響（game server 獨立）
- 重啟後資料從 JSON 恢復

**Q: Game Server 卡住怎麼辦？**
- 房主使用「結束遊戲」
- 端口監控自動檢測並重置

**Q: 版本衝突怎麼辦？**
- 系統自動檢查版本
- 顯示更新提示
- 玩家選擇是否更新

---

## 🎮 三款遊戲說明

### 1. TicTacToe (井字遊戲)
- **類型**: CLI 雙人遊戲
- **操作**: 輸入座標 `row col` (例如: `0 1`)
- **規則**: 3×3 棋盤，先連成三個獲勝
- **展示**: 關卡 A（CLI 雙人）

### 2. Snake Battle (貪吃蛇對戰)
- **類型**: GUI 雙人遊戲（Pygame）
- **操作**: 方向鍵或 WASD
- **規則**: 紅蛇 vs 藍蛇，吃食物得分，撞到對方的蛇就輸
- **展示**: 關卡 B（GUI 介面）

### 3. Blackjack (21點)
- **類型**: CLI 3-6人遊戲
- **操作**: 
  - 下注階段：輸入金額
  - 行動階段：`h`(要牌) / `s`(停牌) / `d`(加倍)
- **規則**: 
  - 目標：點數接近21但不爆牌
  - Blackjack 賠率 2.5倍
  - 一般勝利賠率 2倍
  - 籌碼歸零即破產
- **展示**: 關卡 C（3+人同局）

---

## ⚠️ 故障排除

### 連線失敗
```bash
# 檢查 Server 是否運行
ps aux | grep server

# 確認端口未被佔用
lsof -i :8001
lsof -i :8002
```

### 遊戲無法啟動
- 確認已完整下載遊戲
- 檢查 `downloads/<username>/` 目錄
- 查看遊戲的 config.json

### macOS 端口衝突
- Port 5000 被 AirPlay 佔用
- 系統已改用動態端口分配

### 遊戲視窗未自動開啟
- 確認是 macOS 系統（使用 osascript）
- 檢查終端權限設定

---

## 💡 Demo 技巧

### 準備工作
1. ✅ **清空舊資料** - Demo 前執行 `make clean`
2. ✅ **準備終端** - 至少 5 個終端視窗
3. ✅ **測試流程** - 事先完整跑一次
4. ✅ **記錄帳號** - dev1/dev123, player1/pass123

### 時間分配（總時長 15-20分鐘）
- Server 啟動：1分鐘
- Developer 上架：5分鐘
- Player 下載：2分鐘
- 遊玩展示：5分鐘
- 評分評論：2分鐘
- 口頭問答：5分鐘

### 展示重點
1. **自動化功能** - 遊戲視窗自動開啟、結果自動顯示
2. **完整流程** - 從上架到遊玩到評分一氣呵成
3. **多人遊戲** - Blackjack 展示 3+ 人同局
4. **資料持久化** - 重啟 Server 後資料仍在

### 推薦 Demo 順序
```
1. make clean (清理舊資料)
2. make server (啟動 Servers)
3. make developer (開發者上架三款遊戲)
4. make player (玩家下載 TicTacToe)
5. 兩人對戰（展示自動化）
6. 評分評論
7. （時間充裕）展示 Blackjack 多人
8. make clean (Demo 完成後清理)
```

---

## 📁 重要檔案位置

### Server 端
- `server/lobby_server.py` - 大廳伺服器
- `server/developer_server.py` - 開發者伺服器
- `server/data/*.json` - 資料儲存

### Developer 端
- `developer/developer_client.py` - 開發者客戶端
- `developer/games/tictactoe/` - 井字遊戲
- `developer/games/snakebattle/` - 貪吃蛇對戰
- `developer/games/blackjack/` - 21點

### Player 端
- `player/lobby_client.py` - 玩家客戶端
- `player/downloads/<username>/` - 下載的遊戲

---

## 🏆 評分項目總結

| 項目 | 配分 | 完成度 |
|------|------|--------|
| D1-D3, P1-P4 | 55分 | ✅ 100% |
| 遊戲實作 (A+B+C) | 15分 | ✅ 100% |
| 系統架構 | 5分 | ✅ 100% |
| 使用者體驗 | 5分 | ✅ 100% |
| 程式碼品質 | 5分 | ✅ 100% |
| 口頭問答 | 15分 | ✅ 準備就緒 |
| **總計** | **100分** | **✅ 完整** |

---

## 🎓 預祝 Demo 成功！

**聯絡資訊**: 如有問題請聯絡開發團隊

**最後檢查清單**:
- [ ] `make clean` - 清理舊資料
- [ ] `make server` - Server 端正常啟動
- [ ] `make developer` - Developer 可上架遊戲
- [ ] `make player` - Player 可下載遊玩
- [ ] 三款遊戲都能運行
- [ ] 自動化功能正常
- [ ] 口頭問答準備完成
- [ ] `make clean` - Demo 完成後清理

**快速指令參考**:
```bash
make help      # 查看所有可用指令
make demo      # 顯示快速 Demo 指南
make install   # 安裝遊戲依賴 (pygame)
make clean-all # 完全清理（包含玩家下載）
```

Good luck! 🚀