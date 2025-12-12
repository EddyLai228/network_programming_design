# HW3: Game Store System

一個整合遊戲大廳（Lobby）與遊戲商城（Store）的完整平台，支援開發者上架遊戲、玩家下載遊玩、評分評論等功能。

## 系統架構

本系統分為三個主要部分：

1. **Server 端** - 部署在 Linux 伺服器上
   - Developer Server (Port 8001) - 處理開發者操作
   - Lobby Server (Port 8002) - 處理玩家操作
   - Database Server - 持久化資料儲存

2. **Developer 端** - 遊戲開發者使用
   - Developer Client - 上架、更新、下架遊戲
   - Games 目錄 - 開發中的遊戲

3. **Player 端** - 一般玩家使用
   - Lobby Client - 瀏覽、下載、遊玩遊戲
   - Downloads 目錄 - 下載的遊戲

## 目錄結構

```
hw3/
├── server/                    # 伺服器端
│   ├── developer_server.py    # 開發者伺服器
│   ├── lobby_server.py        # 大廳伺服器
│   ├── db_server.py           # 資料庫伺服器
│   ├── protocol.py            # 通訊協定
│   ├── uploaded_games/        # 上架遊戲儲存區
│   └── data/                  # 資料庫檔案
│
├── developer/                 # 開發者端
│   ├── developer_client.py    # 開發者客戶端
│   ├── protocol.py            # 通訊協定
│   ├── games/                 # 開發中遊戲
│   │   ├── tictactoe/        # 井字遊戲範例
│   │   └── snake/            # 貪食蛇範例
│   └── template/             # 遊戲開發範本
│       └── GAME_SPEC.md      # 遊戲規格文件
│
└── player/                    # 玩家端
    ├── lobby_client.py        # 大廳客戶端
    ├── protocol.py            # 通訊協定
    └── downloads/            # 下載的遊戲
```

## 快速開始

### 1. 環境需求

- Python 3.7+
- 作業系統: Linux, macOS, or Windows
- 網路連線

### 2. 啟動伺服器 (Server 端)

```bash
# 進入 server 目錄
cd hw3/server

# 啟動 Developer Server
python developer_server.py

# 在另一個終端啟動 Lobby Server
python lobby_server.py
```

### 3. 啟動開發者客戶端 (Developer 端)

```bash
# 進入 developer 目錄
cd hw3/developer

# 啟動開發者客戶端 (連接到本地)
python developer_client.py localhost 8001

# 若要連接到遠端伺服器
python developer_client.py <SERVER_IP> 8001
```

### 4. 啟動玩家客戶端 (Player 端)

```bash
# 進入 player 目錄
cd hw3/player

# 啟動玩家客戶端 (連接到本地)
python lobby_client.py localhost 8002

# 若要連接到遠端伺服器
python lobby_client.py <SERVER_IP> 8002
```

## 使用流程

### 開發者流程 (Developer Use Cases)

#### D1: 上架新遊戲

1. 啟動 Developer Client 並登入
2. 選擇「上架新遊戲」
3. 輸入遊戲資訊：
   - 遊戲名稱
   - 簡介
   - 類型 (CLI/GUI/MULTIPLAYER)
   - 最大玩家數
   - 版本號
   - 啟動指令
4. 選擇遊戲目錄（從 `games/` 資料夾）
5. 系統自動打包並上傳
6. 上架成功後可在「我的遊戲」中查看

#### D2: 更新遊戲版本

1. 在主選單選擇「更新遊戲」
2. 從列表選擇要更新的遊戲
3. 輸入新版本號
4. 選擇更新後的遊戲目錄
5. 系統自動上傳新版本

#### D3: 下架遊戲

1. 選擇「下架遊戲」
2. 從列表選擇要下架的遊戲
3. 確認下架操作
4. 遊戲將不再於商城中顯示

### 玩家流程 (Player Use Cases)

#### P1: 瀏覽遊戲商城

1. 啟動 Lobby Client 並登入
2. 選擇「瀏覽遊戲商城」→「瀏覽所有遊戲」
3. 查看遊戲列表，包含：
   - 遊戲名稱、作者
   - 類型、玩家數
   - 版本、評分

#### P2: 下載遊戲

1. 在商城選單選擇「下載/更新遊戲」
2. 從列表選擇要下載的遊戲
3. 系統自動下載並解壓縮
4. 遊戲儲存在 `downloads/<username>/<game_id>/`

#### P3: 建立房間並遊玩

1. 選擇「遊戲房間」→「建立房間」
2. 選擇要遊玩的遊戲
3. 輸入房間名稱
4. 房間建立成功後等待其他玩家加入
5. 手動啟動遊戲客戶端（參考下方遊戲啟動說明）

#### P4: 評分與評論

1. 在商城選擇「查看遊戲詳情」
2. 選擇要評分的遊戲
3. 查看詳細資訊後選擇「是否要評分/評論此遊戲」
4. 輸入評分 (1-5) 和評論內容
5. 提交後可在遊戲詳情中看到

## 遊戲啟動說明

### Tic-Tac-Toe (井字遊戲)

這是一個雙人 CLI 遊戲範例。

**啟動方式：**

1. 首先啟動遊戲伺服器：
```bash
cd downloads/<username>/tictactoe
python game.py server 
```

2. 玩家1啟動客戶端：
```bash
python game.py client --host localhost 
```

3. 玩家2在另一個終端啟動客戶端：
```bash
python game.py client --host localhost 
```

**操作方式：**
- 輸入格式: `row col` (例如: `0 1`)
- 座標範圍: 0-2

### Snake (貪食蛇)

這是一個單人 GUI 遊戲範例。

**啟動方式：**

```bash
cd downloads/<username>/snake
python game.py
```

**操作方式：**
- 使用方向鍵 (↑↓←→) 控制蛇的移動

## 系統特色

### 1. 選單式介面 (Menu-driven Interface)

- 所有操作都透過清楚的選單完成
- 不需要記憶複雜指令
- 每層選單不超過 5 個選項
- 錯誤訊息清楚明確

### 2. 版本管理

- 支援遊戲版本更新
- 玩家可看到本地版本與伺服器版本差異
- 自動處理版本衝突

### 3. 評分與評論系統

- 玩家可為遊玩過的遊戲評分 (1-5星)
- 可撰寫文字評論
- 在遊戲詳情中顯示平均評分和評論

### 4. 帳號系統

- 開發者帳號與玩家帳號分開管理
- 防止重複登入
- 密碼保護

### 5. 持久化儲存

- 所有資料儲存在 JSON 檔案
- 伺服器重啟後資料不遺失
- 包含：使用者資料、遊戲資料、評論、房間

## 開發新遊戲

如果你想開發新遊戲並上架到平台，請參考：

1. **遊戲規格文件**: `developer/template/GAME_SPEC.md`
2. **範例遊戲**: 
   - `developer/games/tictactoe/` - CLI 雙人遊戲
   - `developer/games/snake/` - GUI 單人遊戲

### 遊戲必要結構

```
your_game/
├── game.py          # 主程式
├── config.json      # 設定檔
└── README.md        # 說明文件
```

### config.json 範例

```json
{
  "name": "Your Game Name",
  "description": "Game description",
  "type": "CLI|GUI|MULTIPLAYER",
  "max_players": 2,
  "version": "1.0.0",
  "start_command": "python game.py"
}
```

## 故障排除

### 連線失敗

- 確認伺服器已正常啟動
- 檢查 IP 和 Port 是否正確
- 防火牆設定是否允許連線

### 上傳/下載失敗

- 檢查網路連線
- 確認檔案權限
- 查看伺服器端 log

### 遊戲無法啟動

- 確認遊戲已完整下載
- 檢查 `start_command` 是否正確
- 查看遊戲目錄中的 README

## 技術細節

### 通訊協定

使用基於 JSON 的自定義協定：
- 訊息格式: 4 bytes 長度前綴 + JSON 資料
- 支援檔案傳輸
- 錯誤處理機制

### 資料儲存

使用 JSON 檔案儲存：
- `data/dev_users.json` - 開發者帳號
- `data/player_users.json` - 玩家帳號
- `data/games.json` - 遊戲資料
- `data/reviews.json` - 評論資料
- `data/rooms.json` - 房間資料

### 檔案傳輸

- 遊戲以 ZIP 格式打包傳輸
- 支援斷點續傳（未來改進）
- 自動驗證檔案完整性

## 已知限制

1. 目前遊戲需手動啟動（未來可改進為自動啟動）
2. 房間系統較簡單，未實作即時狀態同步
3. 評論不支援編輯和刪除
4. 未實作玩家間即時通訊

## 未來改進方向

- [ ] 自動啟動遊戲功能
- [ ] 房間即時狀態更新
- [ ] Plugin 系統（房間聊天等）
- [ ] Web 介面
- [ ] 遊戲自動測試
- [ ] 用戶頭像和個人資料
- [ ] 排行榜系統

## 聯絡資訊

如有問題請聯絡開發團隊。

## 授權

本專案為教學目的開發，僅供學習使用。
