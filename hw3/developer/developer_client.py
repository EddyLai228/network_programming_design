"""
Developer Client
Menu-driven interface for game developers
"""

import socket
import os
import sys
import zipfile
import threading
import time
import json
from protocol import Protocol, MessageType, recv_message, send_message, send_file


class DeveloperClient:
    def __init__(self, server_host='localhost', server_port=8001):
        self.server_host = server_host
        self.server_port = server_port
        self.socket = None
        self.username = None
        self.logged_in = False
        self.connected = False
        self.monitor_thread = None
    
    def connect(self):
        """Connect to developer server"""
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
            print("遊戲開發者平台".center(50))
            print("=" * 50)
            
            if self.logged_in:
                print(f"\n歡迎, {self.username}!")
                print("\n1. 我的遊戲")
                print("2. 上架新遊戲")
                print("3. 更新遊戲")
                print("4. 下架遊戲")
                print("5. 登出")
                print("6. 離開")
            else:
                print("\n1. 登入")
                print("2. 註冊")
                print("3. 離開")
            
            print("\n" + "=" * 50)
            choice = input("請選擇功能: ").strip()
            
            if self.logged_in:
                if choice == '1':
                    self.list_my_games()
                elif choice == '2':
                    self.upload_game()
                elif choice == '3':
                    self.update_game()
                elif choice == '4':
                    self.delete_game()
                elif choice == '5':
                    self.logout()
                elif choice == '6':
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
        """Register a new developer account"""
        self.clear_screen()
        print("=" * 50)
        print("開發者註冊".center(50))
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
            send_message(self.socket, MessageType.DEV_REGISTER, {
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
        """Login to developer account"""
        self.clear_screen()
        print("=" * 50)
        print("開發者登入".center(50))
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
            send_message(self.socket, MessageType.DEV_LOGIN, {
                'username': username,
                'password': password
            })
            
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type == MessageType.SUCCESS:
                self.logged_in = True
                self.username = data['username']
                print(f"\n✓ {data['message']}")
            else:
                print(f"\n✗ {data['error']}")
        
        except Exception as e:
            print(f"\n✗ 登入失敗: {e}")
        
        input("\n按 Enter 繼續...")
    
    def logout(self):
        """Logout from account"""
        try:
            send_message(self.socket, MessageType.DEV_LOGOUT, {})
            self.safe_recv_message(self.socket)  # Receive logout confirmation
        except Exception as e:
            print(f"登出時發生錯誤: {e}")
        
        self.logged_in = False
        self.username = None
        print("\n已登出")
        input("按 Enter 繼續...")
    
    def list_my_games(self):
        """List developer's games"""
        self.clear_screen()
        print("=" * 50)
        print("我的遊戲".center(50))
        print("=" * 50)
        
        try:
            send_message(self.socket, MessageType.DEV_LIST_MY_GAMES, {})
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type == MessageType.SUCCESS:
                games = data['games']
                
                if not games:
                    print("\n目前沒有上架的遊戲")
                else:
                    print(f"\n共 {len(games)} 款遊戲:\n")
                    for i, game in enumerate(games, 1):
                        status = "✓ 上架中" if game['active'] else "✗ 已下架"
                        print(f"{i}. {game['name']}")
                        print(f"   ID: {game['game_id']}")
                        print(f"   版本: {game['version']}")
                        print(f"   類型: {game['type']}")
                        print(f"   狀態: {status}")
                        print(f"   建立時間: {game['created_at']}")
                        print()
            else:
                print(f"\n✗ {data['error']}")
        
        except Exception as e:
            print(f"\n✗ 獲取遊戲列表失敗: {e}")
        
        input("\n按 Enter 繼續...")
    
    def upload_game(self):
        """Upload a new game"""
        self.clear_screen()
        print("=" * 50)
        print("上架新遊戲".center(50))
        print("=" * 50)
        
        # Get game information
        game_name = input("\n請輸入遊戲名稱: ").strip()
        if not game_name:
            print("遊戲名稱不能為空")
            input("按 Enter 繼續...")
            return
        
        description = input("請輸入遊戲簡介: ").strip()
        if not description:
            print("遊戲簡介不能為空")
            input("按 Enter 繼續...")
            return
        
        print("\n介面類型:")
        print("1. CLI (命令列介面)")
        print("2. GUI (圖形介面)")
        interface_choice = input("請選擇介面類型 (1-2): ").strip()
        
        interface_map = {'1': 'CLI', '2': 'GUI'}
        interface_type = interface_map.get(interface_choice)
        
        if not interface_type:
            print("無效的介面類型")
            input("按 Enter 繼續...")
            return
        
        print("\n遊戲模式:")
        print("1. 單人遊戲")
        print("2. 多人連線遊戲")
        mode_choice = input("請選擇遊戲模式 (1-2): ").strip()
        
        mode_map = {'1': 'SINGLE', '2': 'MULTIPLAYER'}
        game_mode = mode_map.get(mode_choice)
        
        if not game_mode:
            print("無效的遊戲模式")
            input("按 Enter 繼續...")
            return
        
        # Combine to form game type
        game_type = f"{interface_type}_{game_mode}"  # e.g., "CLI_MULTIPLAYER", "GUI_SINGLE"
        
        max_players = input("請輸入最大玩家數 (預設2): ").strip()
        max_players = int(max_players) if max_players.isdigit() else 2
        
        version = input("請輸入版本號 (預設1.0.0): ").strip()
        version = version if version else "1.0.0"
        
        # Select game directory first
        print("\n請選擇遊戲目錄:")
        games_dir = "games"
        if os.path.exists(games_dir):
            game_dirs = [d for d in os.listdir(games_dir) 
                        if os.path.isdir(os.path.join(games_dir, d))]
            
            if game_dirs:
                for i, d in enumerate(game_dirs, 1):
                    print(f"{i}. {d}")
                
                choice = input("\n請選擇遊戲目錄編號: ").strip()
                if choice.isdigit() and 1 <= int(choice) <= len(game_dirs):
                    game_dir = os.path.join(games_dir, game_dirs[int(choice) - 1])
                else:
                    print("無效的選擇")
                    input("按 Enter 繼續...")
                    return
            else:
                print("games 目錄下沒有找到遊戲")
                input("按 Enter 繼續...")
                return
        else:
            game_dir = input("請輸入遊戲目錄路徑: ").strip()
        
        if not os.path.exists(game_dir):
            print(f"目錄不存在: {game_dir}")
            input("按 Enter 繼續...")
            return
        
        # Try to read commands from config.json
        config_path = os.path.join(game_dir, "config.json")
        server_command = None
        start_command = None
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    server_command = config.get('server_command')
                    start_command = config.get('start_command')
                    print(f"\n✓ 從 config.json 讀取啟動指令:")
                    if server_command:
                        print(f"  伺服器: {server_command}")
                    if start_command:
                        print(f"  客戶端: {start_command}")
            except Exception as e:
                print(f"⚠️  無法讀取 config.json: {e}")
        
        # Ask for commands if not found in config
        if not server_command and game_mode == 'MULTIPLAYER':
            server_command = input("\n請輸入伺服器啟動指令 (例如: python game.py server): ").strip()
            if not server_command:
                print("多人遊戲需要伺服器啟動指令")
                input("按 Enter 繼續...")
                return
        
        if not start_command:
            start_command = input("\n請輸入客戶端啟動指令 (例如: python game.py client --host localhost): ").strip()
            if not start_command:
                print("客戶端啟動指令不能為空")
                input("按 Enter 繼續...")
                return
        
        # Create zip file
        print("\n正在打包遊戲...")
        zip_path = f"/tmp/{game_name}.zip"
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(game_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, game_dir)
                        zipf.write(file_path, arcname)
        except Exception as e:
            print(f"打包遊戲失敗: {e}")
            input("按 Enter 繼續...")
            return
        
        # Upload game
        print("正在上傳遊戲...")
        try:
            upload_data = {
                'game_name': game_name,
                'description': description,
                'game_type': game_type,
                'max_players': max_players,
                'version': version,
                'start_command': start_command
            }
            
            # Add server_command if it exists (for multiplayer games)
            if server_command:
                upload_data['server_command'] = server_command
            
            send_message(self.socket, MessageType.DEV_UPLOAD_GAME, upload_data)
            
            # Wait for ready signal
            msg_type, data = self.safe_recv_message(self.socket)
            if msg_type != MessageType.SUCCESS:
                print(f"✗ {data['error']}")
                input("按 Enter 繼續...")
                return
            
            # Send game file
            send_file(self.socket, zip_path)
            
            # Get final response
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type == MessageType.SUCCESS:
                print(f"\n✓ {data['message']}")
                print(f"遊戲 ID: {data['game_id']}")
            else:
                print(f"\n✗ {data['error']}")
        
        except Exception as e:
            print(f"\n✗ 上傳失敗: {e}")
        
        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)
        
        input("\n按 Enter 繼續...")
    
    def update_game(self):
        """Update an existing game"""
        self.clear_screen()
        print("=" * 50)
        print("更新遊戲".center(50))
        print("=" * 50)
        
        # Get list of games first
        try:
            send_message(self.socket, MessageType.DEV_LIST_MY_GAMES, {})
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type != MessageType.SUCCESS:
                print(f"✗ {data['error']}")
                input("按 Enter 繼續...")
                return
            
            games = data['games']
            active_games = [g for g in games if g['active']]
            
            if not active_games:
                print("\n沒有可更新的遊戲")
                input("按 Enter 繼續...")
                return
            
            # Step 2: 列出開發者已上架的遊戲清單（包含目前版本資訊）
            print("\n你的遊戲列表:\n")
            for i, game in enumerate(active_games, 1):
                print(f"{i}. {game['name']}")
                print(f"   遊戲ID: {game['game_id']}")
                print(f"   當前版本: {game['version']}")
                print(f"   類型: {game['type']}")
                if 'updated_at' in game:
                    print(f"   更新時間: {game['updated_at']}")
                print()
            
            # Step 3: 開發者選擇其中一款要更新的遊戲
            choice = input("請選擇要更新的遊戲編號 (或按 Enter 取消): ").strip()
            if not choice:
                return
            
            if not choice.isdigit() or not (1 <= int(choice) <= len(active_games)):
                print("✗ 無效的選擇")
                input("按 Enter 繼續...")
                return
            
            game = active_games[int(choice) - 1]
            game_id = game['game_id']
            
            print(f"\n準備更新遊戲: {game['name']}")
            print(f"當前版本: {game['version']}")
            print("-" * 50)
            
            # Step 4: 系統引導開發者指定新的版本
            # 4.1 輸入版本號
            new_version = input(f"\n請輸入新版本號: ").strip()
            if not new_version:
                print("✗ 版本號不能為空")
                input("按 Enter 繼續...")
                return
            
            # 驗證版本號格式（基本檢查）
            if not new_version.replace('.', '').replace('-', '').isalnum():
                print("✗ 版本號格式不合法（只能包含字母、數字、點和橫線）")
                input("按 Enter 繼續...")
                return
            
            # 4.2 撰寫更新說明
            update_notes = input("請輸入更新說明 (選填): ").strip()
            
            # 4.3 選擇新檔案來源
            print("\n請選擇遊戲目錄:")
            games_dir = "games"
            if os.path.exists(games_dir):
                game_dirs = [d for d in os.listdir(games_dir) 
                            if os.path.isdir(os.path.join(games_dir, d)) and not d.startswith('.')]
                
                if game_dirs:
                    for i, d in enumerate(game_dirs, 1):
                        print(f"{i}. {d}")
                    
                    dir_choice = input("\n請選擇遊戲目錄編號: ").strip()
                    if dir_choice.isdigit() and 1 <= int(dir_choice) <= len(game_dirs):
                        game_dir = os.path.join(games_dir, game_dirs[int(dir_choice) - 1])
                    else:
                        print("✗ 無效的選擇")
                        input("按 Enter 繼續...")
                        return
                else:
                    print("✗ games 目錄下沒有找到遊戲")
                    input("按 Enter 繼續...")
                    return
            else:
                game_dir = input("請輸入遊戲目錄路徑: ").strip()
            
            # 錯誤處理：若指定的新版本檔案不存在或讀取失敗
            if not os.path.exists(game_dir):
                print(f"✗ 目錄不存在: {game_dir}")
                print("請重新選擇目錄")
                input("按 Enter 繼續...")
                return
            
            if not os.path.isdir(game_dir):
                print(f"✗ 路徑不是目錄: {game_dir}")
                input("按 Enter 繼續...")
                return
            
            # 檢查目錄是否包含遊戲文件
            if not any(os.path.isfile(os.path.join(game_dir, f)) for f in os.listdir(game_dir)):
                print(f"✗ 目錄中沒有找到檔案: {game_dir}")
                input("按 Enter 繼續...")
                return
            
            # Step 5: 開發者確認更新
            print("\n" + "=" * 50)
            print("確認更新資訊:")
            print("=" * 50)
            print(f"遊戲名稱: {game['name']}")
            print(f"舊版本: {game['version']} → 新版本: {new_version}")
            print(f"遊戲目錄: {game_dir}")
            if update_notes:
                print(f"更新說明: {update_notes}")
            print("=" * 50)
            
            confirm = input("\n確認更新? (yes/no): ").strip().lower()
            if confirm not in ['yes', 'y']:
                print("已取消更新")
                input("按 Enter 繼續...")
                return
            
            # Create zip file
            print("\n正在打包遊戲檔案...")
            zip_path = f"/tmp/{game_id}_{new_version}.zip"
            try:
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    file_count = 0
                    for root, dirs, files in os.walk(game_dir):
                        # 排除隱藏文件和 __pycache__
                        files = [f for f in files if not f.startswith('.')]
                        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
                        
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, game_dir)
                            zipf.write(file_path, arcname)
                            file_count += 1
                    
                    print(f"已打包 {file_count} 個檔案")
            except Exception as e:
                print(f"✗ 打包遊戲失敗: {e}")
                input("按 Enter 繼續...")
                return
            
            # Step 6: 系統將新的遊戲內容與版本資訊送到 Server 端
            print("正在上傳到伺服器...")
            try:
                send_message(self.socket, MessageType.DEV_UPDATE_GAME, {
                    'game_id': game_id,
                    'version': new_version,
                    'update_notes': update_notes
                })
                
                # Wait for ready signal
                msg_type, data = self.safe_recv_message(self.socket)
                if msg_type != MessageType.SUCCESS:
                    print(f"✗ {data['error']}")
                    input("按 Enter 繼續...")
                    return
                
                # Send game file
                print("正在傳輸檔案...")
                send_file(self.socket, zip_path)
                
                # Get final response
                msg_type, data = self.safe_recv_message(self.socket)
                
                if msg_type == MessageType.SUCCESS:
                    print(f"\n✓ 更新成功！")
                    print(f"✓ {data['message']}")
                    print(f"遊戲 '{game['name']}' 已更新至版本 {new_version}")
                    print("玩家下載時將自動獲得最新版本")
                else:
                    print(f"\n✗ 更新失敗: {data['error']}")
            
            except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as e:
                # 錯誤處理：若在更新過程中與 Server 連線中斷
                print(f"\n✗ 更新失敗：與伺服器連線中斷")
                print("無法確認伺服器端是否已更新成功")
                print("建議：重新連線後，查看「我的遊戲」確認版本狀態")
                print("如果版本未更新，請重新執行更新操作")
            except Exception as e:
                print(f"\n✗ 更新失敗: {e}")
            
            finally:
                # 清理臨時檔案
                if os.path.exists(zip_path):
                    os.remove(zip_path)
        
        except Exception as e:
            print(f"\n✗ 操作失敗: {e}")
        
        input("\n按 Enter 繼續...")
    
    def delete_game(self):
        """Delete a game"""
        self.clear_screen()
        print("=" * 50)
        print("下架遊戲".center(50))
        print("=" * 50)
        
        # Get list of games first
        try:
            send_message(self.socket, MessageType.DEV_LIST_MY_GAMES, {})
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type != MessageType.SUCCESS:
                print(f"✗ {data['error']}")
                input("按 Enter 繼續...")
                return
            
            games = data['games']
            active_games = [g for g in games if g['active']]
            
            if not active_games:
                print("\n沒有可下架的遊戲")
                input("按 Enter 繼續...")
                return
            
            print("\n選擇要下架的遊戲:\n")
            for i, game in enumerate(active_games, 1):
                print(f"{i}. {game['name']} (版本: {game['version']})")
            
            choice = input("\n請選擇遊戲編號: ").strip()
            if not choice.isdigit() or not (1 <= int(choice) <= len(active_games)):
                print("無效的選擇")
                input("按 Enter 繼續...")
                return
            
            game = active_games[int(choice) - 1]
            game_id = game['game_id']
            
            confirm = input(f"\n確定要下架「{game['name']}」嗎? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("已取消")
                input("按 Enter 繼續...")
                return
            
            send_message(self.socket, MessageType.DEV_DELETE_GAME, {
                'game_id': game_id
            })
            
            msg_type, data = self.safe_recv_message(self.socket)
            
            if msg_type == MessageType.SUCCESS:
                print(f"\n✓ {data['message']}")
            else:
                print(f"\n✗ {data['error']}")
        
        except Exception as e:
            print(f"\n✗ 下架失敗: {e}")
        
        input("\n按 Enter 繼續...")
    
    def run(self):
        """Run the developer client"""
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
            print("\n已離開開發者平台")


if __name__ == "__main__":
    import sys
    
    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8001
    
    client = DeveloperClient(host, port)
    client.run()
