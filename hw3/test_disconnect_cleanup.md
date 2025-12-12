# 測試：斷線自動退出房間

## 測試場景

### 場景 1：玩家主動斷線
1. player1 登入
2. player1 建立房間
3. player1 加入房間
4. player1 關閉客戶端（Ctrl+C）
5. 驗證：房間應該被刪除（因為沒有其他玩家）

### 場景 2：伺服器斷線
1. player1 登入
2. player1 建立房間並加入
3. 關閉伺服器（Ctrl+C）
4. 客戶端會自動斷線退出
5. 重啟伺服器
6. player1 重新登入
7. 驗證：之前的房間應該不存在

### 場景 3：房主斷線，其他玩家還在
1. player1 登入並建立房間
2. player1 加入房間
3. player2 登入並加入同一房間
4. player1（房主）斷線
5. 驗證：
   - player1 被移除
   - player2 成為新房主
   - 房間繼續存在

## 實現邏輯

在 `server/lobby_server.py` 的 `finally` 區塊（第 145-169 行）：

```python
finally:
    if username:
        # Clear session
        self.db.set_player_session(username, None)
        
        # Remove player from any room they were in
        rooms = self.db.get_all_rooms()
        for room_id, room in rooms.items():
            if username in room['players']:
                print(f"Removing {username} from room {room_id} due to disconnection")
                room['players'].remove(username)
                
                # If room is empty, delete it
                if not room['players']:
                    self.db.delete_room(room_id)
                    print(f"Room {room_id} deleted (empty)")
                else:
                    # If host disconnected, assign new host
                    if room['host'] == username:
                        room['host'] = room['players'][0]
                        print(f"New host for room {room_id}: {room['host']}")
                    self.db.update_room(room_id, room)
                break
    
    client_socket.close()
```

## 結論

✅ 無論是客戶端主動斷線，還是伺服器斷線導致客戶端斷線，都會觸發 `finally` 區塊
✅ 自動清理玩家的房間狀態
✅ 自動處理房主轉移
✅ 自動刪除空房間
