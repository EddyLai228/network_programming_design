# System Architecture Diagram

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Game Store System                        │
└─────────────────────────────────────────────────────────────────┘

                    ┌──────────────────┐
                    │  Linux Server    │
                    │   (系計機器)      │
                    └────────┬─────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
            ▼                ▼                ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │  Developer   │ │    Lobby     │ │   Database   │
    │   Server     │ │   Server     │ │   Server     │
    │   :8001      │ │   :8002      │ │   (JSON)     │
    └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
           │                │                │
           │                │                │
    ┌──────▼───────┐ ┌──────▼───────┐      │
    │  Developer   │ │    Player    │      │
    │   Client     │ │   Client     │      │
    │  (開發者端)   │ │  (玩家端)     │      │
    └──────────────┘ └──────────────┘      │
                                            │
                                    ┌───────▼────────┐
                                    │  Persistent    │
                                    │  Storage       │
                                    │  - Users       │
                                    │  - Games       │
                                    │  - Reviews     │
                                    │  - Rooms       │
                                    └────────────────┘
```

## Component Interaction Flow

### Developer Flow (D1-D3)

```
開發者 → Developer Client → Developer Server → Database
                                    ↓
                            Uploaded Games Storage
                                    ↓
                            Available for Players
```

**Detailed Steps:**
```
1. 開發者登入
   Developer → [DEV_LOGIN] → Developer Server
                                    ↓
                              [驗證] → Database
                                    ↓
                              [成功] → Session

2. 上架遊戲 (D1)
   Developer → [DEV_UPLOAD_GAME] → Developer Server
                                          ↓
                                    [驗證權限]
                                          ↓
                                    [接收檔案]
                                          ↓
                                  uploaded_games/
                                          ↓
                                    [儲存資訊]
                                          ↓
                                      Database

3. 更新遊戲 (D2)
   Developer → [DEV_UPDATE_GAME] → Developer Server
                                          ↓
                                    [驗證權限]
                                          ↓
                              uploaded_games/new_version/
                                          ↓
                                    [更新資訊]
                                          ↓
                                      Database

4. 下架遊戲 (D3)
   Developer → [DEV_DELETE_GAME] → Developer Server
                                          ↓
                                    [驗證權限]
                                          ↓
                                  [標記為inactive]
                                          ↓
                                      Database
```

### Player Flow (P1-P4)

```
玩家 → Lobby Client → Lobby Server → Database
                           ↓
                    Uploaded Games
                           ↓
                    Player Downloads
```

**Detailed Steps:**
```
1. 玩家登入
   Player → [PLAYER_LOGIN] → Lobby Server
                                  ↓
                            [驗證] → Database
                                  ↓
                            [成功] → Session

2. 瀏覽商城 (P1)
   Player → [PLAYER_LIST_GAMES] → Lobby Server
                                        ↓
                                  [查詢遊戲]
                                        ↓
                                    Database
                                        ↓
                                  [遊戲列表]
                                        ↓
   Player ← [顯示遊戲資訊+評分] ←─────────┘

3. 下載遊戲 (P2)
   Player → [PLAYER_DOWNLOAD_GAME] → Lobby Server
                                           ↓
                                    [驗證遊戲存在]
                                           ↓
                                       Database
                                           ↓
                                    [讀取遊戲檔案]
                                           ↓
                                   uploaded_games/
                                           ↓
                                     [打包ZIP]
                                           ↓
   Player ← [接收檔案] ←──────────────────────┘
      ↓
   解壓縮
      ↓
   downloads/<username>/<game_id>/

4. 建立房間 (P3)
   Player → [PLAYER_CREATE_ROOM] → Lobby Server
                                          ↓
                                    [驗證遊戲]
                                          ↓
                                      Database
                                          ↓
                                    [建立房間]
                                          ↓
                                      Database
                                          ↓
   Player ← [房間資訊] ←──────────────────┘

5. 評分評論 (P4)
   Player → [PLAYER_REVIEW_GAME] → Lobby Server
                                          ↓
                                  [驗證已遊玩]
                                          ↓
                                      Database
                                          ↓
                                    [儲存評論]
                                          ↓
                                      Database
```

## Data Flow Diagram

```
┌──────────────┐
│  Developer   │
│    Writes    │
│    Game      │
└──────┬───────┘
       │
       ▼
┌──────────────┐    Upload     ┌──────────────┐
│   Developer  │──────────────→│   Developer  │
│    Client    │               │    Server    │
└──────────────┘               └──────┬───────┘
                                      │
                                      ▼
                               ┌──────────────┐
                               │   Uploaded   │
                               │    Games     │
                               └──────┬───────┘
                                      │
                                      │ Download
                                      ▼
                               ┌──────────────┐
                               │    Lobby     │
                               │    Server    │
                               └──────┬───────┘
                                      │
                                      ▼
┌──────────────┐   Download    ┌──────────────┐
│    Player    │←──────────────│    Player    │
│   Downloads  │               │    Client    │
└──────┬───────┘               └──────────────┘
       │
       ▼
┌──────────────┐
│    Player    │
│    Plays     │
│    Game      │
└──────┬───────┘
       │
       │ Rate & Review
       ▼
┌──────────────┐
│   Database   │
│   (Reviews)  │
└──────────────┘
```

## File System Layout

```
hw3/
│
├── server/                         # 伺服器端 (Linux)
│   ├── developer_server.py         # Port 8001
│   ├── lobby_server.py             # Port 8002
│   ├── db_server.py                # 資料庫管理
│   ├── protocol.py                 # 通訊協定
│   ├── start_servers.sh            # 啟動腳本
│   ├── clear_data.sh               # 清理腳本
│   │
│   ├── data/                       # 資料庫檔案
│   │   ├── dev_users.json          # 開發者帳號
│   │   ├── player_users.json       # 玩家帳號
│   │   ├── games.json              # 遊戲資料
│   │   ├── reviews.json            # 評論資料
│   │   └── rooms.json              # 房間資料
│   │
│   └── uploaded_games/             # 上架遊戲
│       └── <game_id>/
│           └── <version>/
│               └── [game files]
│
├── developer/                      # 開發者端
│   ├── developer_client.py         # 開發者客戶端
│   ├── protocol.py                 # 通訊協定
│   ├── start_developer.sh          # 啟動腳本
│   │
│   ├── games/                      # 開發中遊戲
│   │   ├── tictactoe/              # 井字遊戲
│   │   │   ├── game.py
│   │   │   ├── config.json
│   │   │   └── README.md
│   │   └── snake/                  # 貪食蛇
│   │       ├── game.py
│   │       ├── config.json
│   │       └── README.md
│   │
│   └── template/                   # 遊戲範本
│       └── GAME_SPEC.md            # 遊戲規格
│
└── player/                         # 玩家端
    ├── lobby_client.py             # 玩家客戶端
    ├── protocol.py                 # 通訊協定
    ├── start_player.sh             # 啟動腳本
    │
    └── downloads/                  # 下載的遊戲
        └── <username>/             # 每位玩家獨立
            └── <game_id>/
                ├── [game files]
                └── game_info.json
```

## Network Protocol

```
┌─────────────┐                    ┌─────────────┐
│   Client    │                    │   Server    │
└──────┬──────┘                    └──────┬──────┘
       │                                  │
       │  1. Send Request                │
       │  ┌────────────────────────┐     │
       │  │ Length (4 bytes)       │     │
       │  │ JSON Message           │     │
       │  └────────────────────────┘     │
       ├──────────────────────────────→  │
       │                                  │
       │  2. Process Request              │
       │                             ┌────▼────┐
       │                             │ Handler │
       │                             └────┬────┘
       │                                  │
       │  3. Send Response                │
       │  ┌────────────────────────┐     │
       │  │ Length (4 bytes)       │     │
       │  │ JSON Response          │     │
       │  └────────────────────────┘     │
       │  ←──────────────────────────────┤
       │                                  │
       ▼                                  ▼
```

**Message Format:**
```json
{
  "type": "MessageType",
  "data": {
    "field1": "value1",
    "field2": "value2"
  }
}
```

## State Diagram: Developer Session

```
     ┌─────────┐
     │  Start  │
     └────┬────┘
          │
          ▼
     ┌─────────┐
     │Connected│
     └────┬────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
┌────────┐  ┌────────┐
│Register│  │ Login  │
└───┬────┘  └───┬────┘
    │           │
    └─────┬─────┘
          │
          ▼
    ┌──────────┐
    │ Logged In│
    └────┬─────┘
         │
    ┌────┼────┬────┬────┐
    │    │    │    │    │
    ▼    ▼    ▼    ▼    ▼
  ┌───┐┌───┐┌───┐┌───┐┌───┐
  │D1 ││D2 ││D3 ││List│Logout
  │   ││   ││   ││Games│
  └───┘└───┘└───┘└───┘└─┬─┘
                         │
                         ▼
                    ┌─────────┐
                    │   End   │
                    └─────────┘
```

## State Diagram: Player Session

```
     ┌─────────┐
     │  Start  │
     └────┬────┘
          │
          ▼
     ┌─────────┐
     │Connected│
     └────┬────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
┌────────┐  ┌────────┐
│Register│  │ Login  │
└───┬────┘  └───┬────┘
    │           │
    └─────┬─────┘
          │
          ▼
    ┌──────────┐
    │ Logged In│
    └────┬─────┘
         │
    ┌────┼────┬────┬────┐
    │    │    │    │    │
    ▼    ▼    ▼    ▼    ▼
  ┌───┐┌───┐┌───┐┌───┐┌───┐
  │P1 ││P2 ││P3 ││P4 │Logout
  │   ││   ││   ││   │
  └───┘└───┘└─┬─┘└───┘└─┬─┘
              │          │
         ┌────┘          │
         │               │
         ▼               ▼
    ┌─────────┐    ┌─────────┐
    │ In Room │    │   End   │
    └────┬────┘    └─────────┘
         │
    ┌────┼────┐
    │    │    │
    ▼    ▼    ▼
  ┌───┐┌───┐┌───┐
  │Play│Leave│Wait│
  └───┘└───┘└───┘
```

## Game Launch Sequence

```
Player 1              Server              Player 2
   │                    │                    │
   │ Create Room        │                    │
   ├───────────────────→│                    │
   │                    │                    │
   │ Room Created       │                    │
   │←───────────────────┤                    │
   │                    │                    │
   │                    │    Join Room       │
   │                    │←───────────────────┤
   │                    │                    │
   │                    │  Room Joined       │
   │                    ├───────────────────→│
   │                    │                    │
   │  Start Game Server │                    │
   │  (Manual)          │                    │
   │                    │                    │
   │  Launch Client 1   │  Launch Client 2   │
   │  (Manual)          │  (Manual)          │
   │                    │                    │
   ├────────────────────┼───────────────────→│
   │         Game Communication              │
   │←────────────────────────────────────────│
   │                    │                    │
   │         Game Finished                   │
   │                    │                    │
   │  Rate & Review     │  Rate & Review     │
   ├───────────────────→│←───────────────────┤
   │                    │                    │
```

## Summary

This architecture provides:
- ✅ Clear separation of concerns
- ✅ Independent development and deployment
- ✅ Scalable design
- ✅ Easy to maintain and extend
- ✅ Secure communication
- ✅ Persistent data storage

For more details, see:
- [README.md](README.md) - Complete documentation
- [SUMMARY.md](SUMMARY.md) - Implementation summary
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
