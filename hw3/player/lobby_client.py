"""
Lobby Client (Player Client)
Menu-driven interface for players
"""

import socket
import os
import sys
import zipfile
import subprocess
import threading
import time
from protocol import Protocol, MessageType, recv_message, send_message, recv_file, recv_exact


class LobbyClient:
    def __init__(self, server_host='localhost', server_port=8002):
        self.server_host = server_host
        self.server_port = server_port
        self.socket = None
        self.username = None
        self.logged_in = False
        self.downloads_dir = os.path.abspath("downloads")
        self.current_room = None
        self.connected = False
        self.monitor_thread = None
        self.game_server_process = None
        self.game_monitor_thread = None
        self.socket_lock = threading.Lock()  # Protect socket operations
        self.room_monitor_thread = None
        self.room_monitor_active = False
    
    def connect(self):
        """Connect to lobby server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_host, self.server_port))
            self.connected = True
            # Start connection monitor thread
            self.monitor_thread = threading.Thread(target=self._monitor_connection, daemon=True)
            self.monitor_thread.start()
            return True
        except Exception as e:
            print(f"連線失敗: {e}")
            return False
    
    def get_local_game_version(self, game_id):
        """獲取本地已下載遊戲的版本號"""
        if not self.username:
            return None
        
        import json
        user_downloads_dir = os.path.join(self.downloads_dir, self.username)
        game_dir = os.path.join(user_downloads_dir, game_id)
        game_info_path = os.path.join(game_dir, "game_info.json")
        
        if os.path.exists(game_info_path):
            try:
                with open(game_info_path, 'r', encoding='utf-8') as f:
                    game_info = json.load(f)
                return game_info.get('version')
            except:
                pass
        return None
    
    def compare_versions(self, local_version, server_version):
        """比較版本號，返回 True 如果服務器版本較新"""
        if not local_version:
            return False
        
        try:
            local_parts = [int(x) for x in local_version.split('.')]
            server_parts = [int(x) for x in server_version.split('.')]
            
            # 補齊長度
            max_len = max(len(local_parts), len(server_parts))
            local_parts += [0] * (max_len - len(local_parts))
            server_parts += [0] * (max_len - len(server_parts))
            
            return server_parts > local_parts
        except:
            return False
    
    def check_for_updates(self):
        """檢查已下載遊戲是否有更新"""
        notifications = []
        
        try:
            # 獲取所有遊戲列表
            send_message(self.socket, MessageType.PLAYER_LIST_GAMES, {})
            msg_type, data = recv_message(self.socket)
            
            if msg_type == MessageType.SUCCESS:
                games = data.get('games', [])
                
                for game in games:
                    game_id = game['game_id']
                    server_version = game['version']
                    local_version = self.get_local_game_version(game_id)
                    
                    if local_version and self.compare_versions(local_version, server_version):
                        notifications.append(
                            f"{game['name']}: {local_version} → {server_version}"
                        )
        except:
            pass
        
        return notifications
    
    def _monitor_connection(self):
        """Monitor connection status in background"""
        while self.connected:
            try:
                # Try to peek at socket to check if it's still alive
                self.socket.setblocking(False)
                try:
                    data = self.socket.recv(1, socket.MSG_PEEK)
                    if not data:
                        # Connection closed
                        self.connected = False
                        print("\n\n⚠️  伺服器連線已中斷")
                        print("正在關閉客戶端...")
                        os._exit(1)
                except BlockingIOError:
                    # No data available, connection is still alive
                    pass
                finally:
                    self.socket.setblocking(True)
                time.sleep(1)
            except:
                break
    
    def disconnect(self):
        """Disconnect from server"""
        self.connected = False
        if self.socket:
            self.socket.close()
            self.socket = None
    
    def clear_screen(self):
        """Clear terminal screen"""
        os.system('clear' if os.name != 'nt' else 'cls')
    
    def safe_recv_message(self, sock):
        """Safely receive message and raise exception if connection lost"""
        result = recv_message(sock)
        if result is None:
            raise ConnectionResetError("伺服器連線已中斷")
        return result
    
    def show_main_menu(self):
        """Show main menu"""
        while True:
            self.clear_screen()
            print("=" * 50)
            print("遊戲大廳".center(50))
            print("=" * 50)
            
            if self.logged_in:
                print(f"\n歡迎, {self.username}!")
                
                # 檢查是否有遊戲需要更新
                update_notifications = self.check_for_updates()
                if update_notifications:
                    print("\n🔔 更新通知:")
                    for notification in update_notifications:
                        print(f"   • {notification}")
                
                print("\n1. 瀏覽遊戲商城")
                print("2. 我的遊戲")
                print("3. 遊戲房間")
                print("4. 登出")
                print("5. 離開")
            else:
                print("\n1. 登入")
                print("2. 註冊")
                print("3. 離開")
            
            print("\n" + "=" * 50)
            choice = input("請選擇功能: ").strip()
            
            if self.logged_in:
                if choice == '1':
                    self.browse_store_menu()
                elif choice == '2':
                    self.my_games_menu()
                elif choice == '3':
                    self.room_menu()
                elif choice == '4':
                    self.logout()
                elif choice == '5':
                    break
                else:
                    print("無效的選項")
                    input("按 Enter 繼續...")
            else:
                if choice == '1':
                    self.login()
                elif choice == '2':
                    self.register()
                elif choice == '3':
                    break
                else:
                    print("無效的選項")
                    input("按 Enter 繼續...")
    
    def register(self):
        """Register a new player account"""
        self.clear_screen()
        print("=" * 50)
        print("玩家註冊".center(50))
        print("=" * 50)
        
        username = input("\n請輸入用戶名: ").strip()
        if not username:
            print("用戶名不能為空")
            input("按 Enter 繼續...")
            return
        
        password = input("請輸入密碼: ").strip()
        if not password:
            print("密碼不能為空")
            input("按 Enter 繼續...")
            return
        
        try:
            send_message(self.socket, MessageType.PLAYER_REGISTER, {
                'username': username,
                'password': password
            })
            
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type == MessageType.SUCCESS:
                print(f"\n✓ {data['message']}")
            else:
                print(f"\n✗ {data['error']}")
        
        except Exception as e:
            print(f"\n✗ 註冊失敗: {e}")
        
        input("\n按 Enter 繼續...")
    
    def login(self):
        """Login to player account"""
        self.clear_screen()
        print("=" * 50)
        print("玩家登入".center(50))
        print("=" * 50)
        
        username = input("\n請輸入用戶名: ").strip()
        if not username:
            print("用戶名不能為空")
            input("按 Enter 繼續...")
            return
        
        password = input("請輸入密碼: ").strip()
        if not password:
            print("密碼不能為空")
            input("按 Enter 繼續...")
            return
        
        try:
            send_message(self.socket, MessageType.PLAYER_LOGIN, {
                'username': username,
                'password': password
            })
            
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type == MessageType.SUCCESS:
                self.logged_in = True
                self.username = data['username']
                self.current_room = None  # Clear any old room state
                
                # Create user download directory
                user_dir = os.path.join(self.downloads_dir, self.username)
                os.makedirs(user_dir, exist_ok=True)
                
                print(f"\n✓ {data['message']}")
            else:
                print(f"\n✗ {data['error']}")
        
        except Exception as e:
            print(f"\n✗ 登入失敗: {e}")
        
        input("\n按 Enter 繼續...")
    
    def logout(self):
        """Logout from account"""
        try:
            send_message(self.socket, MessageType.PLAYER_LOGOUT, {})
            self.safe_recv_message(self.socket)  # Receive logout confirmation
        except Exception as e:
            print(f"登出時發生錯誤: {e}")
        
        self.logged_in = False
        self.username = None
        self.current_room = None
        print("\n已登出")
        input("按 Enter 繼續...")
    
    def _refresh_room_status(self):
        """Refresh current room status and return notification message"""
        if not self.current_room:
            return None
        
        try:
            # Get updated room info with socket lock
            with self.socket_lock:
                send_message(self.socket, MessageType.PLAYER_LIST_ROOMS, {})
                msg_type, data = recv_message(self.socket)
            
            if msg_type == MessageType.SUCCESS:
                rooms = data.get('rooms', [])
                room_id = self.current_room['room_id']
                
                # Find current room in the list
                for room in rooms:
                    if room['room_id'] == room_id:
                        old_players = set(self.current_room.get('players', []))
                        new_players = set(room.get('players', []))
                        old_status = self.current_room['status']
                        new_status = room['status']
                        
                        notification = None
                        
                        # Check for new players
                        joined_players = new_players - old_players
                        if joined_players:
                            notification = f"🔔 {', '.join(joined_players)} 加入了房間！"
                        
                        # Check for left players
                        left_players = old_players - new_players
                        if left_players:
                            notification = f"🔔 {', '.join(left_players)} 離開了房間"
                        
                        # Check if game started (for non-host players)
                        if old_status == 'waiting' and new_status == 'playing':
                            if self.username != room['host']:
                                # Auto-start game client for non-host players
                                print("\n🎮 房主已開始遊戲！正在自動啟動遊戲客戶端...")
                                self.current_room = room
                                self._auto_start_game_client()
                                return "🎮 遊戲已自動啟動"
                        
                        # Check if game ended (for all players)
                        if old_status == 'playing' and new_status == 'waiting':
                            result = room.get('game_result', '')
                            notification = "\n" + "=" * 50 + "\n"
                            notification += "🎮 遊戲已結束".center(50) + "\n"
                            notification += "=" * 50 + "\n"
                            if result:
                                notification += f"\n遊戲結果:\n{result}\n"
                            else:
                                notification += "\n遊戲已結束\n"
                            notification += "\n房間已重置為等待狀態\n"
                            notification += "=" * 50
                        
                        # Update room data
                        self.current_room = room
                        return notification
                
                # Room not found - it was deleted
                self.current_room = None
                return "⚠️  房間已被刪除"
        except:
            pass
        
        return None
    
    def browse_store_menu(self):
        """Store browsing menu"""
        while True:
            self.clear_screen()
            print("=" * 50)
            print("遊戲商城".center(50))
            print("=" * 50)
            
            print("\n1. 瀏覽所有遊戲")
            print("2. 查看遊戲詳情")
            print("3. 下載/更新遊戲")
            print("4. 返回主選單")
            
            print("\n" + "=" * 50)
            choice = input("請選擇功能: ").strip()
            
            if choice == '1':
                self.list_games()
            elif choice == '2':
                self.view_game_details()
            elif choice == '3':
                self.download_game()
            elif choice == '4':
                break
            else:
                print("無效的選項")
                input("按 Enter 繼續...")
    
    def my_games_menu(self):
        """My games menu"""
        while True:
            self.clear_screen()
            print("=" * 50)
            print("我的遊戲".center(50))
            print("=" * 50)
            
            print("\n1. 查看已下載的遊戲")
            print("2. 返回主選單")
            
            print("\n" + "=" * 50)
            choice = input("請選擇功能: ").strip()
            
            if choice == '1':
                self.list_downloaded_games()
            elif choice == '2':
                break
            else:
                print("無效的選項")
                input("按 Enter 繼續...")
    
    def room_menu(self):
        """Room menu"""
        # Start room monitor thread for auto-game-start detection
        def monitor_room_for_game_start():
            """Background thread to monitor room status and auto-start game"""
            last_status = self.current_room['status'] if self.current_room else None
            
            while self.room_monitor_active and self.current_room:
                time.sleep(1)  # Check every 1 second
                
                if not self.current_room or not self.room_monitor_active:
                    break
                
                try:
                    # Get updated room info using socket lock
                    with self.socket_lock:
                        send_message(self.socket, MessageType.PLAYER_LIST_ROOMS, {})
                        msg_type, data = recv_message(self.socket)
                    
                    if msg_type == MessageType.SUCCESS:
                        rooms = data.get('rooms', [])
                        room_id = self.current_room['room_id']
                        
                        for room in rooms:
                            if room['room_id'] == room_id:
                                new_status = room['status']
                                
                                # Check if game just started (waiting -> playing)
                                if last_status == 'waiting' and new_status == 'playing':
                                    if self.username != room['host']:
                                        # Auto-start game client for non-host players
                                        print("\n\n" + "=" * 50)
                                        print("🎮 房主已開始遊戲！".center(50))
                                        print("正在自動啟動遊戲客戶端...".center(50))
                                        print("=" * 50 + "\n")
                                        self.current_room = room
                                        self._auto_start_game_client()
                                        print("\n✓ 遊戲視窗已自動打開")
                                        print("請切換到遊戲視窗開始遊玩\n")
                                
                                # Check if game ended (playing -> waiting)
                                elif last_status == 'playing' and new_status == 'waiting':
                                    result = room.get('game_result', '')
                                    print("\n\n" + "=" * 50)
                                    print("🎮 遊戲已結束".center(50))
                                    print("=" * 50)
                                    if result:
                                        print(f"\n遊戲結果:\n{result}\n")
                                    else:
                                        print("\n遊戲已結束\n")
                                    print("房間已重置為等待狀態")
                                    print("=" * 50 + "\n")
                                
                                last_status = new_status
                                self.current_room = room
                                break
                except Exception as e:
                    # Ignore errors in background thread
                    pass
        
        # Start monitor thread if in a room
        if self.current_room and self.username != self.current_room.get('host'):
            self.room_monitor_active = True
            self.room_monitor_thread = threading.Thread(target=monitor_room_for_game_start, daemon=True)
            self.room_monitor_thread.start()
        
        try:
            while True:
                self.clear_screen()
                print("=" * 50)
                print("遊戲房間".center(50))
                print("=" * 50)
                
                # Refresh and show notifications AFTER clear screen
                notification = None
                if self.current_room:
                    notification = self._refresh_room_status()
                
                # Show notification if any
                if notification:
                    print(f"\n{notification}")
                
                # Display current room status
                if self.current_room:
                    print(f"\n【當前房間】")
                    print(f"  房間名稱: {self.current_room['room_name']}")
                    print(f"  遊戲: {self.current_room['game_name']}")
                    
                    old_player_count = len(self.current_room.get('players', []))
                    print(f"  人數: {old_player_count}/{self.current_room['max_players']}")
                    print(f"  狀態: {'等待中' if self.current_room['status'] == 'waiting' else '遊戲中'}")
                    
                    # Show player list
                    players = self.current_room.get('players', [])
                    if players:
                        print(f"  玩家: {', '.join(players)}")
                    
                    # Show auto-start status
                    if self.username != self.current_room.get('host') and self.current_room['status'] == 'waiting':
                        print("\n💡 提示: 等待房主開始遊戲時，系統會自動啟動遊戲客戶端")
                
                print("\n1. 查看所有房間")
                print("2. 建立房間")
                print("3. 加入房間")
                print("4. 離開房間")
                print("5. 開始遊戲")
                print("6. 結束遊戲")
                print("7. 返回主選單")
                
                # Show game server status if host and server is running
                if self.current_room and self.username == self.current_room.get('host'):
                    if self.game_server_process and self.game_server_process.poll() is None:
                        print(f"\n💡 遊戲伺服器運行中 (PID: {self.game_server_process.pid})")
                        print("   遊戲會在伺服器停止後自動結束")
                    
                    # Check if game result file exists (game has ended)
                    if self.current_room.get('status') == 'playing':
                        game_id = self.current_room.get('game_id')
                        if game_id:
                            user_downloads_dir = os.path.join(self.downloads_dir, self.username)
                            game_dir = os.path.join(user_downloads_dir, game_id)
                            result_file = os.path.join(game_dir, 'game_result.txt')
                            if os.path.exists(result_file):
                                print(f"\n⚠️  檢測到遊戲已結束！請選擇 [6] 結束遊戲並更新房間狀態")
                
                print("\n" + "=" * 50)
                choice = input("請選擇功能: ").strip()
                
                if choice == '1':
                    self.list_rooms()
                elif choice == '2':
                    self.create_room()
                elif choice == '3':
                    self.join_room()
                    # Restart room monitor if joined a room
                    if self.current_room and self.username != self.current_room.get('host'):
                        self.room_monitor_active = True
                        self.room_monitor_thread = threading.Thread(target=monitor_room_for_game_start, daemon=True)
                        self.room_monitor_thread.start()
                elif choice == '4':
                    self.leave_room()
                    # Stop room monitor when leaving room
                    self.room_monitor_active = False
                elif choice == '5':
                    self.start_game()
                elif choice == '6':
                    self.end_game()
                elif choice == '7':
                    break
                else:
                    print("無效的選項")
                    input("按 Enter 繼續...")
        finally:
            # Stop room monitor thread when leaving room menu
            self.room_monitor_active = False
            if self.room_monitor_thread:
                self.room_monitor_thread.join(timeout=2)
    
    def list_games(self):
        """List all available games"""
        self.clear_screen()
        print("=" * 50)
        print("遊戲列表".center(50))
        print("=" * 50)
        
        try:
            send_message(self.socket, MessageType.PLAYER_LIST_GAMES, {})
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type == MessageType.SUCCESS:
                games = data['games']
                
                if not games:
                    print("\n目前沒有可用的遊戲")
                else:
                    print(f"\n共 {len(games)} 款遊戲:\n")
                    for i, game in enumerate(games, 1):
                        # 檢查本地版本
                        local_version = self.get_local_game_version(game['game_id'])
                        download_status = ""
                        
                        if local_version:
                            if self.compare_versions(local_version, game['version']):
                                download_status = f" - 已下載 (版本: {local_version}) 🔔 有新版本 {game['version']} 可更新"
                            else:
                                download_status = f" - 已下載 (版本: {local_version})"
                        else:
                            download_status = " - 未下載"
                        
                        print(f"{i}. {game['name']}{download_status}")
                        print(f"   作者: {game['author']}")
                        print(f"   類型: {game['type']}")
                        print(f"   玩家數: {game['max_players']}")
                        print(f"   服務器版本: {game['version']}")
                        print(f"   評分: {'★' * int(game['rating'])}{'☆' * (5 - int(game['rating']))} ({game['rating']}/5.0)")
                        print()
            else:
                print(f"\n✗ {data['error']}")
        
        except Exception as e:
            print(f"\n✗ 獲取遊戲列表失敗: {e}")
        
        input("\n按 Enter 繼續...")
    
    def view_game_details(self):
        """View game details and reviews"""
        self.clear_screen()
        print("=" * 50)
        print("遊戲詳情".center(50))
        print("=" * 50)
        
        # First list games
        try:
            send_message(self.socket, MessageType.PLAYER_LIST_GAMES, {})
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type != MessageType.SUCCESS:
                print(f"\n✗ {data['error']}")
                input("按 Enter 繼續...")
                return
            
            games = data['games']
            
            if not games:
                print("\n目前沒有可用的遊戲")
                input("按 Enter 繼續...")
                return
            
            print("\n選擇要查看的遊戲:\n")
            for i, game in enumerate(games, 1):
                print(f"{i}. {game['name']}")
            
            choice = input("\n請選擇遊戲編號: ").strip()
            if not choice.isdigit() or not (1 <= int(choice) <= len(games)):
                print("無效的選擇")
                input("按 Enter 繼續...")
                return
            
            game = games[int(choice) - 1]
            game_id = game['game_id']
            
            # Get detailed info
            send_message(self.socket, MessageType.PLAYER_GAME_DETAILS, {
                'game_id': game_id
            })
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type == MessageType.SUCCESS:
                game_info = data['game']
                
                self.clear_screen()
                print("=" * 50)
                print(f"{game_info['name']}".center(50))
                print("=" * 50)
                
                print(f"\n作者: {game_info['author']}")
                print(f"類型: {game_info['type']}")
                print(f"玩家數: {game_info['max_players']}")
                print(f"版本: {game_info['version']}")
                print(f"評分: {'★' * int(game_info['rating'])}{'☆' * (5 - int(game_info['rating']))} ({game_info['rating']}/5.0)")
                print(f"評論數: {game_info['review_count']}")
                print(f"\n簡介:\n{game_info['description']}")
                print(f"\n建立時間: {game_info['created_at']}")
                print(f"更新時間: {game_info['updated_at']}")
                
                # Show reviews
                print("\n" + "-" * 50)
                view_reviews = input("\n是否查看評論? (yes/no): ").strip().lower()
                
                if view_reviews == 'yes':
                    send_message(self.socket, MessageType.PLAYER_LIST_REVIEWS, {
                        'game_id': game_id
                    })
                    msg_type, data = self.safe_recv_message(self.socket)
                    
                    if msg_type == MessageType.SUCCESS:
                        reviews = data['reviews']
                        
                        if reviews:
                            print("\n" + "=" * 50)
                            print("玩家評論".center(50))
                            print("=" * 50)
                            
                            for review in reviews[:5]:  # Show first 5 reviews
                                print(f"\n玩家: {review['username']}")
                                print(f"評分: {'★' * int(review['rating'])}{'☆' * (5 - int(review['rating']))} ({review['rating']}/5.0)")
                                if review['comment']:
                                    print(f"評論: {review['comment']}")
                                print(f"時間: {review['created_at']}")
                                print("-" * 50)
                        else:
                            print("\n尚無評論")
                
                # Ask if want to rate/review
                print("\n" + "-" * 50)
                rate_game = input("\n是否要評分/評論此遊戲? (yes/no): ").strip().lower()
                
                if rate_game == 'yes':
                    self.rate_review_game(game_id)
            else:
                print(f"\n✗ {data['error']}")
        
        except Exception as e:
            print(f"\n✗ 操作失敗: {e}")
        
        input("\n按 Enter 繼續...")
    
    def rate_review_game(self, game_id):
        """Rate and review a game"""
        print("\n" + "=" * 50)
        print("評分與評論".center(50))
        print("=" * 50)
        
        try:
            rating_str = input("\n請輸入評分 (1-5): ").strip()
            if not rating_str.replace('.', '').isdigit():
                print("評分必須是數字")
                return
            
            rating = float(rating_str)
            if rating < 1 or rating > 5:
                print("評分必須在1-5之間")
                return
            
            comment = input("請輸入評論 (可選，按Enter跳過): ").strip()
            
            send_message(self.socket, MessageType.PLAYER_REVIEW_GAME, {
                'game_id': game_id,
                'rating': rating,
                'comment': comment
            })
            
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type == MessageType.SUCCESS:
                print(f"\n✓ {data['message']}")
            else:
                print(f"\n✗ {data['error']}")
        
        except Exception as e:
            print(f"\n✗ 評分失敗: {e}")
    
    def download_game(self):
        """Download or update a game"""
        self.clear_screen()
        print("=" * 50)
        print("下載/更新遊戲".center(50))
        print("=" * 50)
        
        # First list games
        try:
            send_message(self.socket, MessageType.PLAYER_LIST_GAMES, {})
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type != MessageType.SUCCESS:
                print(f"\n✗ {data['error']}")
                input("按 Enter 繼續...")
                return
            
            games = data['games']
            
            if not games:
                print("\n目前沒有可用的遊戲")
                input("按 Enter 繼續...")
                return
            
            print("\n選擇要下載的遊戲:\n")
            for i, game in enumerate(games, 1):
                # Check if already downloaded
                user_game_dir = os.path.join(self.downloads_dir, self.username, game['game_id'])
                status = "已下載" if os.path.exists(user_game_dir) else "未下載"
                print(f"{i}. {game['name']} - {status} (版本: {game['version']})")
            
            choice = input("\n請選擇遊戲編號: ").strip()
            if not choice.isdigit() or not (1 <= int(choice) <= len(games)):
                print("無效的選擇")
                input("按 Enter 繼續...")
                return
            
            game = games[int(choice) - 1]
            game_id = game['game_id']
            
            print(f"\n正在下載「{game['name']}」...")
            
            # Send download request
            send_message(self.socket, MessageType.PLAYER_DOWNLOAD_GAME, {
                'game_id': game_id
            })
            
            # Receive game info
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type != MessageType.SUCCESS:
                print(f"✗ {data['error']}")
                input("按 Enter 繼續...")
                return
            
            version = data['version']
            start_command = data['start_command']
            
            # Receive game file
            user_game_dir = os.path.join(self.downloads_dir, self.username, game_id)
            zip_path = os.path.join(user_game_dir, "game.zip")
            
            os.makedirs(user_game_dir, exist_ok=True)
            
            if not recv_file(self.socket, zip_path):
                print("✗ 下載遊戲檔案失敗")
                input("按 Enter 繼續...")
                return
            
            # Extract zip file
            print("正在解壓縮...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(user_game_dir)
            os.remove(zip_path)
            
            # Save game info
            import json
            game_info = {
                'game_id': game_id,
                'name': game['name'],
                'version': version,
                'start_command': start_command
            }
            
            with open(os.path.join(user_game_dir, 'game_info.json'), 'w') as f:
                json.dump(game_info, f, indent=2)
            
            # Get final response
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type == MessageType.SUCCESS:
                print(f"\n✓ {data['message']}")
                print(f"遊戲已儲存至: {user_game_dir}")
            else:
                print(f"\n✗ {data['error']}")
        
        except Exception as e:
            print(f"\n✗ 下載失敗: {e}")
        
        input("\n按 Enter 繼續...")
    
    def list_downloaded_games(self):
        """List downloaded games"""
        self.clear_screen()
        print("=" * 50)
        print("已下載的遊戲".center(50))
        print("=" * 50)
        
        user_dir = os.path.join(self.downloads_dir, self.username)
        
        if not os.path.exists(user_dir):
            print("\n尚未下載任何遊戲")
            input("按 Enter 繼續...")
            return
        
        game_dirs = [d for d in os.listdir(user_dir) 
                    if os.path.isdir(os.path.join(user_dir, d))]
        
        if not game_dirs:
            print("\n尚未下載任何遊戲")
            input("按 Enter 繼續...")
            return
        
        print(f"\n共 {len(game_dirs)} 款遊戲:\n")
        
        import json
        for i, game_dir in enumerate(game_dirs, 1):
            game_path = os.path.join(user_dir, game_dir)
            info_file = os.path.join(game_path, 'game_info.json')
            
            if os.path.exists(info_file):
                with open(info_file, 'r') as f:
                    info = json.load(f)
                print(f"{i}. {info['name']}")
                print(f"   版本: {info['version']}")
                print(f"   位置: {game_path}")
                print()
            else:
                print(f"{i}. {game_dir}")
                print(f"   位置: {game_path}")
                print()
        
        input("\n按 Enter 繼續...")
    
    def list_rooms(self):
        """List all rooms"""
        self.clear_screen()
        print("=" * 50)
        print("房間列表".center(50))
        print("=" * 50)
        
        try:
            send_message(self.socket, MessageType.PLAYER_LIST_ROOMS, {})
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type == MessageType.SUCCESS:
                rooms = data['rooms']
                
                if not rooms:
                    print("\n目前沒有可用的房間")
                else:
                    print(f"\n共 {len(rooms)} 個房間:\n")
                    for i, room in enumerate(rooms, 1):
                        print(f"{i}. {room['room_name']}")
                        print(f"   房間ID: {room['room_id']}")
                        print(f"   遊戲: {room['game_name']} (v{room.get('game_version', '1.0.0')})")
                        print(f"   房主: {room['host']}")
                        print(f"   人數: {len(room['players'])}/{room['max_players']}")
                        print(f"   狀態: {room['status']}")
                        print()
            else:
                print(f"\n✗ {data['error']}")
        
        except Exception as e:
            print(f"\n✗ 獲取房間列表失敗: {e}")
        
        input("\n按 Enter 繼續...")
    
    def create_room(self):
        """Create a new room"""
        self.clear_screen()
        print("=" * 50)
        print("建立房間".center(50))
        print("=" * 50)
        
        try:
            # Scan local downloads directory for games
            user_downloads_dir = os.path.join(self.downloads_dir, self.username)
            
            if not os.path.exists(user_downloads_dir):
                print("\n您尚未下載任何遊戲")
                print("請先到商店下載遊戲後再建立房間")
                input("\n按 Enter 繼續...")
                return
            
            downloaded_games = []
            
            # Scan all game directories
            for item in os.listdir(user_downloads_dir):
                game_path = os.path.join(user_downloads_dir, item)
                game_info_path = os.path.join(game_path, "game_info.json")
                config_path = os.path.join(game_path, "config.json")
                
                # Check if it's a valid game directory
                if os.path.isdir(game_path) and os.path.exists(game_info_path):
                    try:
                        import json
                        # Read game_info.json for game_id and name
                        with open(game_info_path, 'r', encoding='utf-8') as f:
                            game_info = json.load(f)
                        
                        # Read config.json for additional info
                        config = {}
                        if os.path.exists(config_path):
                            with open(config_path, 'r', encoding='utf-8') as f:
                                config = json.load(f)
                        
                        game_id = game_info.get('game_id', item)
                        game_name = game_info.get('name', item)
                        
                        downloaded_games.append({
                            'game_id': game_id,
                            'name': game_name,
                            'max_players': config.get('max_players', 1),
                            'version': game_info.get('version', config.get('version', '1.0.0'))
                        })
                    except Exception as e:
                        # Skip invalid game directories
                        continue
            
            if not downloaded_games:
                print("\n您尚未下載任何遊戲")
                print("請先到商店下載遊戲後再建立房間")
                input("\n按 Enter 繼續...")
                return
            
            print("\n選擇遊戲 (已下載的遊戲):\n")
            for i, game in enumerate(downloaded_games, 1):
                print(f"{i}. {game['name']} v{game['version']} (最多{game['max_players']}人)")
            
            choice = input("\n請選擇遊戲編號: ").strip()
            if not choice.isdigit() or not (1 <= int(choice) <= len(downloaded_games)):
                print("無效的選擇")
                input("按 Enter 繼續...")
                return
            
            game = downloaded_games[int(choice) - 1]
            game_id = game['game_id']
            
            room_name = input(f"\n請輸入房間名稱 (預設: {self.username}的房間): ").strip()
            if not room_name:
                room_name = f"{self.username}的房間"
            
            # Create room
            send_message(self.socket, MessageType.PLAYER_CREATE_ROOM, {
                'game_id': game_id,
                'room_name': room_name
            })
            
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type == MessageType.SUCCESS:
                print(f"\n✓ {data['message']}")
                room_data = data['room_data']
                print(f"房間ID: {room_data['room_id']}")
                print(f"遊戲: {room_data['game_name']}")
                print(f"\n提示: 房間已建立，請選擇「3. 加入房間」來進入房間")
            else:
                print(f"\n✗ {data['error']}")
        
        except Exception as e:
            print(f"\n✗ 建立房間失敗: {e}")
        
        input("\n按 Enter 繼續...")
    
    def join_room(self):
        """Join a room"""
        self.clear_screen()
        print("=" * 50)
        print("加入房間".center(50))
        print("=" * 50)
        
        # Check if already in a room
        if self.current_room:
            print(f"\n✗ 你已經在房間中: {self.current_room['room_name']}")
            print("請先離開當前房間再加入其他房間")
            input("按 Enter 繼續...")
            return
        
        # First list rooms
        try:
            send_message(self.socket, MessageType.PLAYER_LIST_ROOMS, {})
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type != MessageType.SUCCESS:
                print(f"\n✗ {data['error']}")
                input("按 Enter 繼續...")
                return
            
            rooms = data['rooms']
            waiting_rooms = [r for r in rooms if r['status'] == 'waiting']
            
            if not waiting_rooms:
                print("\n目前沒有可加入的房間")
                input("按 Enter 繼續...")
                return
            
            print("\n選擇房間:\n")
            for i, room in enumerate(waiting_rooms, 1):
                game_id = room.get('game_id')
                room_version = room.get('game_version', '1.0.0')
                local_version = self.get_local_game_version(game_id) if game_id else None
                
                version_status = ""
                if not local_version:
                    version_status = " ⚠️  未安裝"
                elif local_version != room_version:
                    version_status = f" ⚠️  版本不符 (你的: v{local_version})"
                else:
                    version_status = " ✓ 版本匹配"
                
                print(f"{i}. {room['room_name']} - {room['game_name']} (v{room_version}){version_status}")
                print(f"   人數: {len(room['players'])}/{room['max_players']}")
            
            choice = input("\n請選擇房間編號: ").strip()
            if not choice.isdigit() or not (1 <= int(choice) <= len(waiting_rooms)):
                print("無效的選擇")
                input("按 Enter 繼續...")
                return
            
            room = waiting_rooms[int(choice) - 1]
            room_id = room['room_id']
            game_id = room.get('game_id')
            
            # Get local game version
            local_version = None
            if game_id:
                local_version = self.get_local_game_version(game_id)
            
            if not local_version:
                print(f"\n✗ 你尚未下載此遊戲或遊戲文件損壞")
                print("請先下載遊戲後再加入房間")
                input("\n按 Enter 繼續...")
                return
            
            # Join room with version check
            send_message(self.socket, MessageType.PLAYER_JOIN_ROOM, {
                'room_id': room_id,
                'game_version': local_version
            })
            
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type == MessageType.SUCCESS:
                print(f"\n✓ {data['message']}")
                self.current_room = data['room_data']
            else:
                print(f"\n✗ {data['error']}")
        
        except Exception as e:
            print(f"\n✗ 加入房間失敗: {e}")
        
        input("\n按 Enter 繼續...")
    
    def leave_room(self):
        """Leave current room"""
        if not self.current_room:
            print("\n你目前不在任何房間中")
            input("按 Enter 繼續...")
            return
        
        try:
            send_message(self.socket, MessageType.PLAYER_LEAVE_ROOM, {
                'room_id': self.current_room['room_id']
            })
            
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type == MessageType.SUCCESS:
                print(f"\n✓ {data['message']}")
                self.current_room = None
            else:
                print(f"\n✗ {data['error']}")
        
        except Exception as e:
            print(f"\n✗ 離開房間失敗: {e}")
        
        input("按 Enter 繼續...")
    
    def start_game(self):
        """Start game in current room (host only)"""
        if not self.current_room:
            print("\n請先建立或加入房間")
            input("按 Enter 繼續...")
            return
        
        # Only host can start the game
        if self.username != self.current_room['host']:
            print("\n只有房主可以開始遊戲")
            print("請等待房主啟動遊戲...")
            input("\n按 Enter 繼續...")
            return
        
        print("\n正在啟動遊戲...")
        
        try:
            # Get game info from current room
            game_id = self.current_room['game_id']
            game_name = self.current_room['game_name']
            max_players = self.current_room['max_players']
            current_players = len(self.current_room.get('players', []))
            
            print(f"遊戲: {game_name}")
            print(f"房間人數: {current_players}/{max_players}")
            
            # Check if room is full
            if current_players < max_players:
                print(f"\n⚠️  房間人數不足 ({current_players}/{max_players})")
                print("等待其他玩家加入...")
                input("\n按 Enter 繼續...")
                return
            
            # Notify server to start game (server will launch game server)
            try:
                send_message(self.socket, MessageType.PLAYER_START_GAME, {
                    'room_id': self.current_room['room_id']
                })
                msg_type, response = self.safe_recv_message(self.socket)
                if msg_type != MessageType.SUCCESS:
                    print(f"\n✗ 無法啟動遊戲: {response.get('error', '未知錯誤')}")
                    input("\n按 Enter 繼續...")
                    return
                
                # Update room data with game port and host
                self.current_room = response.get('room_data', self.current_room)
                game_host = self.current_room.get('game_host', 'localhost')
                game_port = self.current_room.get('game_port')
                
                print(f"✓ {response.get('message', '遊戲已開始')}")
                print(f"✓ 遊戲服務器地址: {game_host}:{game_port}")
                print("\n遊戲服務器已在遠程啟動，請稍候...")
                time.sleep(2)
                
            except Exception as e:
                print(f"\n✗ 通知服務器失敗: {e}")
                input("\n按 Enter 繼續...")
                return
            
            # All players (including host) launch game client
            self._launch_game_client()
            
        except Exception as e:
            print(f"\n✗ 啟動遊戲失敗: {e}")
            import traceback
            traceback.print_exc()
        
        input("\n按 Enter 繼續...")
    
    def _launch_game_client(self):
        """Launch game client to connect to remote game server"""
        try:
            import json
            import subprocess
            
            game_id = self.current_room['game_id']
            game_name = self.current_room['game_name']
            game_host = self.current_room.get('game_host', self.server_host)
            game_port = self.current_room.get('game_port')
            
            if not game_port:
                print("\n✗ 無法獲取遊戲端口")
                return
            
            # Find game directory
            user_downloads_dir = os.path.join(self.downloads_dir, self.username)
            game_dir = os.path.join(user_downloads_dir, game_id)
            
            if not os.path.exists(game_dir):
                print(f"\n✗ 找不到遊戲目錄: {game_dir}")
                print("請先下載遊戲")
                return
            
            # Read game config
            config_path = os.path.join(game_dir, "config.json")
            if not os.path.exists(config_path):
                print(f"\n✗ 找不到遊戲配置文件")
                return
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            game_type = config.get('type', 'GUI')
            start_command = config.get('start_command', 'python game.py')
            
            # Parse start command
            cmd_parts = start_command.split()
            if cmd_parts[0] == 'python':
                cmd_parts[0] = 'python3'
            
            # Add connection parameters
            cmd_parts.extend(['--host', game_host, '--port', str(game_port)])
            
            print(f"\n正在連接到遊戲服務器...")
            print(f"地址: {game_host}:{game_port}")
            
            # Start game client
            if 'CLI' in game_type:
                # Start in new terminal for CLI games
                import platform
                system = platform.system()
                
                if system == 'Darwin':  # macOS
                    terminal_cmd = [
                        'osascript', '-e',
                        f'tell app "Terminal" to do script "cd {game_dir} && {" ".join(cmd_parts)}; echo \'遊戲已結束，3秒後自動關閉視窗...\'; sleep 3; exit"'
                    ]
                elif system == 'Linux':
                    terminal_cmd = ['x-terminal-emulator', '-e', f'cd {game_dir} && {" ".join(cmd_parts)}']
                else:  # Windows
                    terminal_cmd = ['start', 'cmd', '/k', f'cd {game_dir} && {" ".join(cmd_parts)}']
                
                subprocess.Popen(terminal_cmd, shell=(system == 'Windows'))
                print(f"✓ 遊戲客戶端已在新終端窗口啟動")
            else:
                # Start in background for GUI games
                process = subprocess.Popen(
                    cmd_parts,
                    cwd=game_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                print(f"✓ 遊戲已啟動 (PID: {process.pid})")
            
            print("\n提示: 遊戲客戶端已啟動並連接到遠程服務器")
            print("      遊戲結束後請關閉遊戲窗口")
            
        except Exception as e:
            print(f"\n✗ 啟動遊戲客戶端失敗: {e}")
            import traceback
            traceback.print_exc()
    
    def _monitor_game_server(self, process, room_id):
        """Monitor game server process and auto-end game when it exits"""
        try:
            # Wait for process to complete
            stdout, stderr = process.communicate()
            
            # Process has ended, capture output as game result
            result_lines = []
            
            if stdout:
                # Get last few lines as result
                lines = stdout.strip().split('\n')
                # Take last 10 lines or less
                result_lines = lines[-10:] if len(lines) > 10 else lines
            
            result = '\n'.join(result_lines) if result_lines else "遊戲已結束"
            
            print(f"\n\n🎮 遊戲伺服器已停止，正在自動結束遊戲...")
            
            # Send end game message to server
            try:
                send_message(self.socket, MessageType.PLAYER_END_GAME, {
                    'room_id': room_id,
                    'result': result
                })
                
                msg_type, data = recv_message(self.socket)
                
                if msg_type == MessageType.SUCCESS:
                    print(f"✓ 房間已自動重置為等待狀態")
                    self.current_room = data.get('room_data', self.current_room)
                else:
                    print(f"⚠️  無法自動重置房間: {data.get('error', '未知錯誤')}")
            except Exception as e:
                print(f"⚠️  自動結束遊戲失敗: {e}")
            
        except Exception as e:
            print(f"\n⚠️  監控遊戲伺服器時發生錯誤: {e}")
        finally:
            self.game_server_process = None
            self.game_monitor_thread = None
    
    def end_game(self):
        """Force end game (for emergency situations)"""
        if not self.current_room:
            print("\n你目前不在任何房間中")
            input("按 Enter 繼續...")
            return
        
        # Only host can force end the game
        if self.username != self.current_room['host']:
            print("\n只有房主可以結束遊戲")
            input("\n按 Enter 繼續...")
            return
        
        if self.current_room['status'] != 'playing':
            print("\n房間目前沒有進行中的遊戲")
            input("\n按 Enter 繼續...")
            return
        
        # Check if game has ended by looking for result file
        game_result = None
        game_id = self.current_room.get('game_id')
        if game_id:
            user_downloads_dir = os.path.join(self.downloads_dir, self.username)
            game_dir = os.path.join(user_downloads_dir, game_id)
            result_file = os.path.join(game_dir, 'game_result.txt')
            if os.path.exists(result_file):
                try:
                    with open(result_file, 'r', encoding='utf-8') as f:
                        game_result = f.read().strip()
                    print(f"\n✓ 檢測到遊戲結果: {game_result}")
                    print("\n正在更新房間狀態...")
                except:
                    pass
        
        if not game_result:
            print("\n⚠️  結束遊戲")
            
            confirm = input("\n確定要結束遊戲? 輸入 'yes' 確認: ").strip().lower()
            
            if confirm != 'yes':
                print("\n已取消")
                input("按 Enter 繼續...")
                return
            game_result = '遊戲被結束'
        
        try:
            # Force terminate game server if it's running
            if self.game_server_process and self.game_server_process.poll() is None:
                print("\n正在終止遊戲伺服器進程...")
                self.game_server_process.terminate()
                try:
                    self.game_server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print("結束遊戲進程...")
                    self.game_server_process.kill()
            
            send_message(self.socket, MessageType.PLAYER_END_GAME, {
                'room_id': self.current_room['room_id'],
                'result': game_result
            })
            
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type == MessageType.SUCCESS:
                print(f"\n✓ {data['message']}")
                self.current_room = data['room_data']
                print("\n房間已重置為等待狀態")
            else:
                print(f"\n✗ {data['error']}")
        
        except Exception as e:
            print(f"\n✗ 結束失敗: {e}")
        
        input("\n按 Enter 繼續...")
    
    def _auto_start_game_client(self):
        """Auto-start game client for non-host players - Connect to remote game server"""
        try:
            import json
            import subprocess
            import time
            
            game_id = self.current_room['game_id']
            game_name = self.current_room['game_name']
            game_host = self.current_room.get('game_host', self.server_host)
            game_port = self.current_room.get('game_port')
            
            if not game_port:
                print(f"\n✗ 無法獲取遊戲端口")
                return
            
            # Find game directory
            user_downloads_dir = os.path.join(self.downloads_dir, self.username)
            game_dir = os.path.join(user_downloads_dir, game_id)
            
            if not os.path.exists(game_dir):
                print(f"\n✗ 找不到遊戲目錄: {game_dir}")
                print("請先下載遊戲")
                return
            
            # Read game config
            config_path = os.path.join(game_dir, "config.json")
            if not os.path.exists(config_path):
                print(f"\n✗ 找不到遊戲配置文件")
                return
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            game_type = config.get('type', 'GUI')
            start_command = config.get('start_command', 'python game.py')
            
            # Parse start command
            cmd_parts = start_command.split()
            if cmd_parts[0] == 'python':
                cmd_parts[0] = 'python3'
            
            # Add connection parameters to remote game server
            cmd_parts.extend(['--host', game_host, '--port', str(game_port)])
            
            print(f"連接到遊戲服務器: {game_host}:{game_port}")
            print("等待伺服器就緒...")
            time.sleep(2)
            
            # Start game client in new terminal
            if 'CLI' in game_type:
                import platform
                system = platform.system()
                
                if system == 'Darwin':  # macOS
                    terminal_cmd = [
                        'osascript', '-e',
                        f'tell app "Terminal" to do script "cd {game_dir} && {" ".join(cmd_parts)}; echo \'遊戲已結束，3秒後自動關閉視窗...\'; sleep 3; exit"'
                    ]
                elif system == 'Linux':
                    terminal_cmd = ['x-terminal-emulator', '-e', f'cd {game_dir} && {" ".join(cmd_parts)}']
                else:  # Windows
                    terminal_cmd = ['start', 'cmd', '/k', f'cd {game_dir} && {" ".join(cmd_parts)}']
                
                subprocess.Popen(terminal_cmd, shell=(system == 'Windows'))
                print(f"✓ 遊戲客戶端已在新終端窗口啟動")
            else:
                # For GUI games - save logs to file for debugging
                log_file = os.path.join(game_dir, 'client.log')
                with open(log_file, 'w') as log:
                    process = subprocess.Popen(
                        cmd_parts,
                        cwd=game_dir,
                        stdout=log,
                        stderr=subprocess.STDOUT
                    )
                print(f"✓ 遊戲已啟動 (PID: {process.pid})")
                print(f"   日誌文件: {log_file}")
            
            time.sleep(1)
            
        except Exception as e:
            print(f"\n✗ 自動啟動遊戲失敗: {e}")
    
    def run(self):
        """Run the lobby client"""
        if not self.connect():
            print("無法連接到伺服器")
            return
        
        try:
            self.show_main_menu()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as e:
            print("\n\n⚠️  伺服器連線已中斷")
            print("請重新啟動伺服器後再試")
        except KeyboardInterrupt:
            print("\n\n使用者中斷")
        finally:
            self.disconnect()
            print("\n已離開遊戲大廳")


if __name__ == "__main__":
    import sys
    
    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8002
    
    client = LobbyClient(host, port)
    client.run()
