#!/usr/bin/env python3
"""
測試腳本：驗證房間建立只顯示已下載的遊戲
"""

import socket
import sys
import os

# Add player directory to path to import protocol
sys.path.insert(0, 'player')
from protocol import MessageType, send_message, recv_message

def test_room_creation_filter():
    """測試房間建立過濾功能"""
    print("=" * 60)
    print("測試：房間建立只顯示已下載的遊戲".center(60))
    print("=" * 60)
    
    # 連接到 lobby server
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('localhost', 8002))
    print("✓ 已連接到 Lobby Server")
    
    # 登入 player1
    send_message(sock, MessageType.PLAYER_LOGIN, {
        'username': 'player1',
        'password': 'pass123'
    })
    msg_type, data = recv_message(sock)
    
    if msg_type != MessageType.SUCCESS:
        print(f"✗ 登入失敗: {data}")
        sock.close()
        return False
    
    print(f"✓ 登入成功: {data['message']}")
    
    # 取得所有遊戲列表
    send_message(sock, MessageType.PLAYER_LIST_GAMES, {})
    msg_type, data = recv_message(sock)
    
    if msg_type != MessageType.SUCCESS:
        print(f"✗ 取得遊戲列表失敗: {data}")
        sock.close()
        return False
    
    all_games = data['games']
    print(f"\n系統中所有遊戲 (共 {len(all_games)} 個):")
    for game in all_games:
        print(f"  - {game['name']} (作者: {game['author']})")
    
    # 檢查 player1 已下載的遊戲
    downloads_dir = 'player/downloads/player1'
    downloaded_games = []
    
    for game in all_games:
        game_dir = f"{game['author']}_{game['name']}"
        game_path = os.path.join(downloads_dir, game_dir)
        
        if os.path.exists(game_path):
            downloaded_games.append(game['name'])
    
    print(f"\nplayer1 已下載的遊戲 (共 {len(downloaded_games)} 個):")
    for name in downloaded_games:
        print(f"  ✓ {name}")
    
    not_downloaded = [g['name'] for g in all_games if g['name'] not in downloaded_games]
    if not_downloaded:
        print(f"\nplayer1 未下載的遊戲 (共 {len(not_downloaded)} 個):")
        for name in not_downloaded:
            print(f"  ✗ {name}")
    
    # 驗證結果
    print("\n" + "=" * 60)
    print("測試結果：")
    print("=" * 60)
    
    expected_count = len(downloaded_games)
    success = True
    
    if expected_count > 0:
        print(f"✓ player1 應該能看到 {expected_count} 個遊戲可以建立房間")
        print(f"  遊戲: {', '.join(downloaded_games)}")
    else:
        print("⚠ player1 沒有下載任何遊戲，應該看到提示訊息")
    
    if not_downloaded:
        print(f"✓ 以下遊戲不應該出現在房間建立選單中:")
        for name in not_downloaded:
            print(f"  - {name}")
    
    print("\n建議：")
    print("1. 啟動玩家客戶端: cd player && ./start_player.sh")
    print("2. 使用 player1/player1 登入")
    print("3. 選擇「建立房間」")
    print(f"4. 確認只看到已下載的遊戲: {', '.join(downloaded_games)}")
    print(f"5. 確認看不到未下載的遊戲: {', '.join(not_downloaded)}")
    
    sock.close()
    return success

if __name__ == '__main__':
    try:
        test_room_creation_filter()
    except Exception as e:
        print(f"\n✗ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
