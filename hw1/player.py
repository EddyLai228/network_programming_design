import socket
import threading
import json
import time
import sys
import os

sys.path.append(os.path.dirname(__file__))

class PlayerA:
    def __init__(self, username, password, lobby_host=None, lobby_port=12000, register_mode=False):
        self.username = username
        self.password = password
        self.register_mode = register_mode
        
        # Lobby server connection - 自動檢測或使用預設
        if lobby_host is None:
            self.lobby_host = self.detect_lobby_server()
        else:
            self.lobby_host = lobby_host
        self.lobby_port = lobby_port
        self.lobby_socket = None
        self.logged_in = False
        
        # UDP scanning
        self.udp_socket = None
        self.scan_range = range(10000, 10021)  # Ports to scan
        self.target_hosts = [
            'localhost',         # Local testing alternative
            '140.113.235.151',  # linux1.cs.nycu.edu.tw
            '140.113.235.152',  # linux2.cs.nycu.edu.tw
            '140.113.235.153',  # linux3.cs.nycu.edu.tw
            '140.113.235.154'  # linux4.cs.nycu.edu.tw
        ]
        
        # TCP connection server
        self.tcp_socket = None
        self.tcp_port = None
        self.opponent_socket = None
        self.opponent_name = None
        self.connected = False
        
        # Threading
        self.tcp_thread = None
        self.input_thread = None
        self.lobby_monitor_thread = None
        
        # Store scan results
        self.last_scan_results = []
        
        # Game state
        self.in_game = False
        self.my_choice = None
        self.opponent_choice = None
        self.my_score = 0
        self.opponent_score = 0
        self.waiting_for_choice = False
        
        # Two-phase game state
        self.game_phase = 'rock_paper_scissors'  # 'rock_paper_scissors' or 'direction'
        self.rps_winner = None  # 'player_a', 'player_b', or 'tie'
        self.rps_loser = None   # 'player_a', 'player_b', or None
        self.my_direction = None
        self.opponent_direction = None
        self.direction_turn_order = []  # [first_chooser, second_chooser]
        self.game_completed = True  # 遊戲是否完成，可以開始新一輪
        self.game_started = False  # 遊戲是否已開始
        
        # Penalty control for connection termination
        self.should_apply_penalty_on_exit = True
    
    def detect_lobby_server(self):
        """自動檢測 lobby server 位置"""
        try:
            import socket
            import subprocess
            
            # 方法1: 檢查是否在 NYCU 網域內
            hostname = socket.gethostname()
            print(f"🔍 檢測到主機名: {hostname}")
            
            if 'linux' in hostname and 'cs.nycu.edu.tw' in hostname:
                lobby_ip = '127.0.0.1' 
                print(f"🏫 檢測到 NYCU 環境，使用 lobby server: {lobby_ip}")
                return lobby_ip
            
            # 方法2: 嘗試連接各個可能的 lobby server
            potential_servers = [
                '140.113.235.151',  # linux1
                '140.113.235.152',  # linux2
                '140.113.235.153',  # linux3  
                '140.113.235.154',  # linux4
                '127.0.0.1'         # localhost
            ]
            
            for server_ip in potential_servers:
                try:
                    # 快速檢測端口是否開放
                    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    test_socket.settimeout(1.0)  # 1秒超時
                    result = test_socket.connect_ex((server_ip, self.lobby_port))
                    test_socket.close()
                    
                    if result == 0:  # 連接成功
                        print(f"✅ 找到可用的 lobby server: {server_ip}")
                        return server_ip
                        
                except:
                    continue
            
            # 方法3: 預設值
            default_ip = '127.0.0.1'
            print(f"⚠️ 無法自動檢測 lobby server，使用預設: {default_ip}")
            return default_ip
            
        except Exception as e:
            print(f"❌ Lobby server 檢測失敗: {e}")
            return '127.0.0.1'  # 預設值
    
    def connect_to_lobby(self):
        """Connect and login to the lobby server"""
        try:
            print(f"🔗 正在連接到 lobby server: {self.lobby_host}:{self.lobby_port}")
            self.lobby_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.lobby_socket.connect((self.lobby_host, self.lobby_port))
            
            if self.register_mode:
                # 註冊模式 - 先嘗試註冊
                print(f"📝 正在註冊新帳號 '{self.username}'...")
                register_request = {
                    'action': 'register',
                    'username': self.username,
                    'password': self.password
                }
                
                self.lobby_socket.send(json.dumps(register_request).encode('utf-8'))
                response_data = self.lobby_socket.recv(1024).decode('utf-8')
                response = json.loads(response_data)
                
                if response['status'] == 'success':
                    print(f"✓ 註冊成功！歡迎 {self.username}")
                    # 註冊成功後自動登入
                    self.register_mode = False  # 避免遞迴呼叫
                    return self.connect_to_lobby()
                else:
                    print(f"✗ 註冊失敗: {response['message']}")
                    return False
            else:
                # 登入模式
                print(f"🔐 正在登入帳號 '{self.username}'...")
                login_request = {
                    'action': 'login',
                    'username': self.username,
                    'password': self.password
                }
                
                self.lobby_socket.send(json.dumps(login_request).encode('utf-8'))
                response_data = self.lobby_socket.recv(1024).decode('utf-8')
                response = json.loads(response_data)
                
                if response['status'] == 'success':
                    print(f"✓ 登入成功！歡迎回來 {self.username}")
                    if 'user_data' in response:
                        user_data = response['user_data']
                        print(f"  等級: {user_data['level']}, 經驗值: {user_data['experience_points']} XP")
                        print(f"  遊戲幣: {user_data['in_game_currency']}, 登入次數: {user_data['login_count']}")
                    self.logged_in = True
                    
                    # 啟動 lobby 連線監控
                    self.start_lobby_monitor()
                    return True
                else:
                    print(f"✗ 登入失敗: {response['message']}")
                    return False
                
        except Exception as e:
            print(f"✗ Error connecting to lobby server: {e}")
            return False
    
    def scan_for_players(self):
        """Scan for available Player B instances"""
        print("🔍 Scanning for available players...")
        available_players = []
        
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.settimeout(0.1)  # 0.1 second timeout per request
            
            scan_message = {
                'type': 'scan',
                'from_player': self.username
            }
            message_data = json.dumps(scan_message).encode('utf-8')
            
            # Scan each host and port combination
            for host in self.target_hosts:
                print(f"  🔍 Scanning {host}... (ports {self.scan_range.start}-{self.scan_range.stop-1})")
                found_on_host = 0
                for port in self.scan_range:
                    try:
                        # Send scan request
                        self.udp_socket.sendto(message_data, (host, port))
                        
                        # Wait for response
                        try:
                            response_data, address = self.udp_socket.recvfrom(1024)
                            response = json.loads(response_data.decode('utf-8'))
                            
                            if (response.get('type') == 'scan_response' and 
                                response.get('status') == 'available'):
                                
                                player_info = {
                                    'name': response.get('player'),
                                    'host': address[0],
                                    'port': address[1],
                                    'response_port': response.get('port', address[1])
                                }
                                available_players.append(player_info)
                                found_on_host += 1
                                print(f"    ✓ Found {player_info['name']} at {address[0]}:{address[1]}")
                        
                        except socket.timeout:
                            continue
                        except json.JSONDecodeError:
                            continue
                    
                    except Exception as e:
                        continue
                
                # 顯示每個主機的掃描結果
                if found_on_host > 0:
                    print(f"    ✅ Found {found_on_host} players on {host}")
                else:
                    print(f"    ❌ No players found on {host}")
            
            self.udp_socket.close()
            
        except Exception as e:
            print(f"Error during scan: {e}")
        
        print(f"📊 掃描完成，找到 {len(available_players)} 個在線玩家")
        return available_players
    
    def display_available_players(self, players):
        """Display list of available players"""
        if not players:
            print("❌ 沒有找到在線玩家，請確認其他玩家已經啟動")
            return None
        
        print("\n📋 在線玩家列表:")
        for i, player in enumerate(players):
            print(f"  • {player['name']} (位於 {player['host']}:{player['port']})")
        
        return players
    
    def select_player(self, players):
        """Let user select a player to invite"""
        while True:
            try:
                choice = input(f"\nSelect player (1-{len(players)}) or 'r' to rescan: ").strip()
                
                if choice.lower() == 'r':
                    return 'rescan'
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(players):
                    return players[choice_num - 1]
                else:
                    print(f"Please enter a number between 1 and {len(players)}")
            
            except ValueError:
                print("Invalid input. Please enter a number or 'r' to rescan.")
            except (KeyboardInterrupt, EOFError):
                return None
    
    def send_invitation(self, player_info):
        """Send game invitation to selected player"""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.settimeout(10.0)  # 10 second timeout for response
            
            invitation_message = {
                'type': 'invitation',
                'from_player': self.username,
                'game_type': 'Guessing-Game',
                'timestamp': time.time()
            }
            
            message_data = json.dumps(invitation_message).encode('utf-8')
            target_address = (player_info['host'], player_info['port'])
            
            print(f"📨 正在邀請 {player_info['name']} (位於 {target_address[0]}:{target_address[1]})...")
            print("⏳ 等待回應中...")
            
            # Send invitation
            self.udp_socket.sendto(message_data, target_address)
            
            # Wait for response
            try:
                response_data, address = self.udp_socket.recvfrom(1024)
                response = json.loads(response_data.decode('utf-8'))
                
                if (response.get('type') == 'invitation_response' and 
                    response.get('accepted') == True):
                    
                    print(f"✓ {player_info['name']} accepted the invitation!")
                    self.opponent_name = player_info['name']
                    
                    # Start TCP server and send connection info
                    if self.start_tcp_server():
                        self.send_tcp_connection_info(player_info, target_address)
                        return True
                    else:
                        print("Failed to start TCP server")
                        return False
                
                elif (response.get('type') == 'invitation_response' and 
                      response.get('accepted') == False):
                    
                    print(f"✗ {player_info['name']} declined the invitation.")
                    return False
                
                else:
                    print("Invalid response received")
                    return False
            
            except socket.timeout:
                print("⏰ Invitation timed out. Player may be busy or unavailable.")
                return False
            
            except json.JSONDecodeError:
                print("Received invalid response")
                return False
        
        except Exception as e:
            print(f"Error sending invitation: {e}")
            return False
        
        finally:
            if self.udp_socket:
                self.udp_socket.close()
    
    def start_tcp_server(self):
        """Start TCP server for the connection"""
        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Try to bind to a port above 15000 with larger range for busy servers
            for port in range(15000, 16000):
                try:
                    self.tcp_socket.bind(('127.0.0.1', port))  # 綁定到本機
                    self.tcp_port = port
                    print(f"🔗 TCP服務器綁定到端口: {port}")
                    break
                except OSError as e:
                    continue
            
            if not self.tcp_port:
                raise Exception("No available TCP port found in range 15000-16000")
            
            self.tcp_socket.listen(1)
            print(f"✓ TCP server started on port {self.tcp_port}")
            
            # Start server thread
            self.tcp_thread = threading.Thread(target=self.accept_tcp_connection, daemon=True)
            self.tcp_thread.start()
            
            return True
        
        except Exception as e:
            print(f"Error starting TCP server: {e}")
            return False
    
    def send_tcp_connection_info(self, player_info, udp_address):
        """Send TCP connection information to the invited player"""
        try:
            # 使用本機回環地址，與TCP服務器綁定地址保持一致
            local_ip = "127.0.0.1"
            print(f"🔍 使用本機回環地址: {local_ip}")
            
            connection_info = {
                'type': 'tcp_connection',
                'tcp_host': local_ip,
                'tcp_port': self.tcp_port,
                'from_player': self.username
            }
            
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            message_data = json.dumps(connection_info).encode('utf-8')
            udp_socket.sendto(message_data, udp_address)
            udp_socket.close()
            
            print(f"📡 Sent TCP connection info to {player_info['name']}")
            
        except Exception as e:
            print(f"Error sending connection info: {e}")
    
    def accept_tcp_connection(self):
        """Accept incoming TCP connection from Player B"""
        try:
            print("⏳ Waiting for opponent to connect...")
            self.tcp_socket.settimeout(30.0)  # 30 second timeout
            
            client_socket, address = self.tcp_socket.accept()
            self.opponent_socket = client_socket
            
            print(f"✓ Opponent connected from {address[0]}:{address[1]}")
            
            # Wait for opponent identification
            client_socket.settimeout(10.0)
            data = client_socket.recv(1024).decode('utf-8')
            
            if data:
                try:
                    handshake = json.loads(data)
                    if handshake.get('type') == 'handshake':
                        self.opponent_name = handshake.get('player_name', 'Unknown')
                        print(f"✓ Connected to {self.opponent_name}")
                        
                        # Send handshake response
                        response = {
                            'type': 'handshake_response',
                            'player_name': self.username,
                            'status': 'ready'
                        }
                        client_socket.send(json.dumps(response).encode('utf-8'))
                        
                        # Initialize connection
                        self.connected = True
                        self.initialize_connection()
                        
                        # Start message loop
                        self.message_loop()
                    else:
                        print("❌ Invalid handshake received")
                        client_socket.close()
                except json.JSONDecodeError:
                    print("❌ Invalid handshake data")
                    client_socket.close()
            else:
                print("❌ No handshake received")
                client_socket.close()
            
        except socket.timeout:
            print("⏰ Connection timed out. Opponent didn't connect.")
            self.cleanup_tcp_server()
        except Exception as e:
            print(f"Error accepting connection: {e}")
            self.cleanup_tcp_server()
    
    def initialize_connection(self):
        """Initialize the connection session"""
        try:
            if not self.opponent_name:
                print("❌ 無法建立連線：對手名稱未知")
                return False
                
            print(f"\n✓ 連線建立成功!")
            print(f"📍 你是 {self.username}")
            print(f"🤝 對手: {self.opponent_name}")
            print("=" * 50)
            print("連線已建立，可以開始遊戲！")
            print("=" * 50)
            print("🎮 兩階段遊戲：猜拳 + 猜方向")
            print("🎯 規則說明：")
            print("  • 第一階段：猜拳 (剪刀石頭布)")
            print("  • 第二階段：猜方向 (上下左右)")
            print("  • 猜拳輸的人先選方向，贏的人後選")
            print("  • 如果猜拳贏的人選的方向和輸的人一樣 → 猜拳贏的人最終獲勝")
            print("  • 如果方向不一樣 → 平手")
            print("💡 第一階段指令:")
            print("  • 1 - 剪刀 ✂️")
            print("  • 2 - 石頭 🪨")
            print("  • 3 - 布 📄")
            print("💡 第二階段指令:")
            print("  • 4 - 上 ⬆️")
            print("  • 5 - 下 ⬇️")
            print("  • 6 - 左 ⬅️")
            print("  • 7 - 右 ➡️")
            print("  • quit - 離開遊戲")
            print("=" * 50)
            
            self.in_game = True
            self.start_game()
            
            # Start input handling in separate thread
            import threading
            self.input_thread = threading.Thread(target=self.handle_connection_input, daemon=True)
            self.input_thread.start()
            
            return True
        
        except Exception as e:
            print(f"Error initializing connection: {e}")
            self.end_connection()
    
    def handle_connection_input(self):
        """Handle user input during connection session"""
        try:
            while self.connected:
                command_input = input(f"{self.username} 輸入指令: ").strip()
                
                if not command_input:
                    # 空輸入 (Enter) - 只有在遊戲完全結束且仍連接時才開始新一輪
                    if self.game_completed and self.connected:
                        self.start_game()
                    elif self.game_phase == 'rock_paper_scissors':
                        if not self.waiting_for_choice and not self.my_choice:
                            print("🎯 請選擇你的猜拳：")
                            print("1 - 剪刀 ✂️")
                            print("2 - 石頭 🪨")
                            print("3 - 布 📄")
                        elif self.waiting_for_choice:
                            print("⏳ 等待對手選擇...")
                    elif self.game_phase == 'direction':
                        # 在方向選擇階段，顯示當前狀態
                        if not self.my_direction:
                            # 使用與輸入處理相同的邏輯檢查是否輪到我選擇
                            can_choose = False
                            
                            if self.direction_turn_order and self.direction_turn_order[0] == 'player_a':
                                # 我是第一個選擇的
                                can_choose = True
                            elif (self.rps_winner == 'player_a' and self.opponent_direction):
                                # 我猜拳贏了，對手先選完了，現在輪到我
                                can_choose = True
                            elif (self.direction_turn_order and len(self.direction_turn_order) > 1 and 
                                  self.direction_turn_order[1] == 'player_a' and self.opponent_direction):
                                # 按照輪次順序，我是第二個，且對手已選擇
                                can_choose = True
                            
                            if can_choose:
                                print("🎯 現在輪到你選擇方向：")
                                self.show_direction_choices()
                            else:
                                if not self.opponent_direction:
                                    print(f"⏳ 等待 {self.opponent_name} 先選擇方向...")
                                else:
                                    print("❌ 現在不是你選擇方向的時候")
                        else:
                            if not self.opponent_direction:
                                print(f"⏳ 等待 {self.opponent_name} 選擇方向...")
                            else:
                                print("⏳ 等待最終結果...")
                    continue
                    
                command_parts = command_input.split()
                command = command_parts[0].lower()
                
                if command == 'quit':
                    self.handle_quit_in_game()
                    return
                    
                elif command in ['1', '2', '3', '4', '5', '6', '7']:
                    if self.game_phase == 'rock_paper_scissors':
                        # 第一階段：猜拳
                        if command in ['1', '2', '3'] and not self.waiting_for_choice:
                            choice_map = {'1': 'scissors', '2': 'rock', '3': 'paper'}
                            choice_emoji = {'1': '✂️', '2': '🪨', '3': '📄'}
                            choice_name = {'1': '剪刀', '2': '石頭', '3': '布'}
                            
                            self.my_choice = choice_map[command]
                            print(f"你選擇了: {choice_name[command]} {choice_emoji[command]}")
                            
                            # 只通知對手輪到他了，不透露選擇內容
                            self.send_game_message({
                                'type': 'your_turn'
                            })
                            
                            self.waiting_for_choice = True
                            print(f"等待 {self.opponent_name} 選擇中...")
                            print(f"⚠️ 等待中，請不要輸入任何內容，只需按 Enter 等待！")
                        elif command in ['1', '2', '3'] and self.waiting_for_choice:
                            print("請等待對手選擇完畢")
                        elif command in ['4', '5', '6', '7']:
                            print("❌ 現在是猜拳階段，請選擇 1-3")
                    
                    elif self.game_phase == 'direction':
                        # 第二階段：猜方向
                        if command in ['4', '5', '6', '7']:
                            # 檢查是否輪到我選擇方向
                            if not self.my_direction:
                                # 檢查是否輪到我選擇
                                can_choose = False
                                
                                if self.direction_turn_order and self.direction_turn_order[0] == 'player_a':
                                    # 我是第一個選擇的
                                    can_choose = True
                                elif (self.rps_winner == 'player_a' and self.opponent_direction):
                                    # 我猜拳贏了，對手先選完了，現在輪到我
                                    can_choose = True
                                elif (self.direction_turn_order and len(self.direction_turn_order) > 1 and 
                                      self.direction_turn_order[1] == 'player_a' and self.opponent_direction):
                                    # 按照輪次順序，我是第二個，且對手已選擇
                                    can_choose = True
                                
                                if can_choose:
                                    self.handle_direction_choice(command)
                                else:
                                    if not self.opponent_direction:
                                        print(f"⏳ 請等待 {self.opponent_name} 先選擇方向...")
                                    else:
                                        print("❌ 現在不是你選擇方向的時候")
                            else:
                                print("❌ 你已經選擇過方向了")
                        elif command in ['1', '2', '3']:
                            print("❌ 現在是方向選擇階段，請選擇 4-7")
                    
                else:
                    print("❌ 未知指令。可用指令:")
                    if self.game_phase == 'rock_paper_scissors':
                        print("  • 1 - 剪刀 ✂️")
                        print("  • 2 - 石頭 🪨")
                        print("  • 3 - 布 📄")
                    elif self.game_phase == 'direction':
                        print("  • 4 - 上 ⬆️")
                        print("  • 5 - 下 ⬇️")
                        print("  • 6 - 左 ⬅️")
                        print("  • 7 - 右 ➡️")
                    print("  • quit - 離開遊戲")
                    
        except KeyboardInterrupt:
            print(f"\n⚠️ 收到中斷信號...")
            if self.in_game or (hasattr(self, 'game_started') and self.game_started):
                self.handle_quit_in_game()
            else:
                print("\n🚪 連線被中斷")
                self.end_connection()
            return
        except Exception as e:
            print(f"輸入處理錯誤: {e}")
            return
    
    def show_connection_status(self):
        """Show current connection status"""
        print(f"\n{'='*50}")
        print(f"🔗 連線狀態")
        print(f"📍 你是: {self.username}")
        if self.opponent_name:
            print(f"🤝 對手: {self.opponent_name}")
        print(f"{'='*50}")

    def send_message(self, message_text):
        """Send simple text message to opponent via TCP"""
        try:
            if self.opponent_socket:
                message = {
                    'type': 'message',
                    'content': message_text,
                    'from': self.username
                }
                message_str = json.dumps(message)
                self.opponent_socket.send(message_str.encode('utf-8'))
                print(f"→ 傳送: {message_text}")
                return True
            return False
        except Exception as e:
            print(f"Error sending message: {e}")
            return False
    
    def message_loop(self):
        """Main message loop for receiving opponent messages"""
        try:
            while self.opponent_socket:
                self.opponent_socket.settimeout(1.0)
                try:
                    data = self.opponent_socket.recv(1024).decode('utf-8')
                    if not data:
                        print("🔌 對手已斷線")
                        # 如果在遊戲進行中，給自己獎勵
                        if self.in_game and not self.game_completed:
                            print("🎉 對手中途斷線，你獲得了 100 經驗值獎勵！")
                            self.update_user_stats(100, 0)
                        break
                    
                    # 處理可能連在一起的多個JSON消息
                    self.process_received_data(data)
                
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"Error receiving message: {e}")
                    break
        
        except KeyboardInterrupt:
            print(f"\n⚠️ 收到中斷信號，正在結束遊戲連接...")
            # 通知對手離開
            if self.in_game or (hasattr(self, 'game_started') and self.game_started):
                self.handle_quit_in_game()
        except Exception as e:
            print(f"Message loop error: {e}")
        
        finally:
            print("🏁 Message loop ended")
            self.end_connection()
    
    def process_received_data(self, data):
        """處理接收到的數據，可能包含多個JSON消息"""
        # 嘗試分割可能連在一起的JSON消息
        messages = []
        buffer = data
        
        while buffer:
            try:
                # 嘗試解析JSON
                message, idx = json.JSONDecoder().raw_decode(buffer)
                messages.append(message)
                buffer = buffer[idx:].strip()
            except json.JSONDecodeError:
                # 如果無法解析，嘗試找到下一個'{'
                start_idx = buffer.find('{', 1)
                if start_idx != -1:
                    # 嘗試解析第一部分
                    try:
                        first_part = buffer[:start_idx]
                        message = json.loads(first_part)
                        messages.append(message)
                        buffer = buffer[start_idx:]
                    except json.JSONDecodeError:
                        print(f"收到無效訊息: {data}")
                        break
                else:
                    print(f"收到無效訊息: {data}")
                    break
        
        # 處理所有解析成功的消息
        for message in messages:
            self.handle_opponent_message(message)

    def handle_opponent_message(self, message):
        """Handle messages from opponent"""
        msg_type = message.get('type')
        
        if msg_type == 'message':
            content = message.get('content', '')
            from_user = message.get('from', 'Unknown')
            print(f"← {from_user}: {content}")
        
        elif msg_type == 'system':
            content = message.get('content', '')
            print(f"🔔 系統: {content}")
            
        elif msg_type == 'player_choice':
            if self.game_phase == 'rock_paper_scissors':
                self.opponent_choice = message.get('choice')
                # 當收到對手選擇後，發送自己的選擇並判斷勝負
                if self.my_choice and self.opponent_choice:
                    # 發送自己的選擇給對手
                    self.send_game_message({
                        'type': 'player_choice',
                        'choice': self.my_choice,
                        'player': self.username
                    })
                    self.determine_winner()
        
        elif msg_type == 'direction_choice':
            # 收到對手的方向選擇（隱藏不顯示）
            self.opponent_direction = message.get('direction')
            print(f"{self.opponent_name} 已完成方向選擇")
            
            # 如果我也選完了，判斷最終結果
            if self.my_direction and self.opponent_direction:
                self.determine_final_winner()
            elif not self.my_direction:
                # 檢查是否輪到我選擇
                if (self.rps_loser == 'player_b' and self.rps_winner == 'player_a'):
                    # 對手輸了先選，現在輪到我選
                    print(f"🎯 現在輪到你選擇方向：")
                    self.show_direction_choices()
                elif self.direction_turn_order and len(self.direction_turn_order) > 1 and self.direction_turn_order[1] == 'player_a':
                    # 按照輪次順序，第二個是我
                    print(f"🎯 現在輪到你選擇方向：")
                    self.show_direction_choices()
        
        elif msg_type == 'waiting_choice':
            phase = message.get('game_phase', 'rock_paper_scissors')
            if phase == 'rock_paper_scissors':
                print(f"{self.username} 選擇中...")
            elif phase == 'direction':
                print(f"{self.username} 選擇方向中...")
        
        elif msg_type == 'opponent_quit':
            quit_message = message.get('message', '對手已離開遊戲')
            reward_winner = message.get('reward_winner', False)
            
            print(f"⚠️ {quit_message}")
            
            # 如果對手在遊戲中離開，給予留下的玩家獎勵
            if reward_winner and (self.game_started and not self.game_completed):
                print("🎁 對手遊戲中途離開，你獲得 100 XP 獎勵！")
                self.update_user_stats(100, 0)
                print("⭐ 已獲得 100 經驗值！")
            
            # 完全重置遊戲狀態
            self.reset_game_state()
            print("🚪 遊戲結束，正在退出...")
            self.end_connection(apply_penalty=False)  # 對手離開時不懲罰自己
            return
        
        elif msg_type == 'disconnect':
            print("⚠️ 對手已斷線，遊戲結束")
            # 如果在遊戲進行中，給自己獎勵
            if self.in_game and not self.game_completed:
                print("🎉 對手中途斷線，你獲得了 100 經驗值獎勵！")
                self.update_user_stats(100, 0)
            
            # 完全重置遊戲狀態
            self.reset_game_state()
            self.end_connection(apply_penalty=False)  # 對手斷線時不懲罰自己
            return
        
        else:
            print(f"收到未知訊息類型: {msg_type}")
    
    def handle_quit_in_game(self):
        """處理遊戲中途退出的邏輯"""
        # 檢查是否在遊戲進行中（已開始但未結束）
        if self.in_game and not self.game_completed:
            print("⚠️ 遊戲進行中離開將被扣除 100 XP!")
            
            # 通知對手玩家退出並獲得獎勵
            self.send_game_message({
                'type': 'opponent_quit',
                'message': f'{self.username} 已離開遊戲',
                'reward_winner': True  # 告知對手可獲得獎勵
            })
            
            # 扣除經驗值
            self.update_user_stats(-100, 0)
            print("💸 已扣除 100 XP 作為懲罰")
            print(f"🎁 對手 {self.opponent_name} 將獲得 100 XP 獎勵")
            
            print("🚪 離開遊戲...")
        else:
            print("🚪 離開遊戲...")
        
        self.end_connection()
    
    def update_user_stats(self, exp_change, currency_change):
        """更新用戶統計（經驗值和遊戲幣）"""
        stats = {}
        if exp_change != 0:
            stats['experience_points'] = exp_change
        if currency_change != 0:
            stats['in_game_currency'] = currency_change
        
        if stats:
            self.update_lobby_stats(stats)
    
    def reset_game_state(self):
        """重置所有遊戲狀態變量"""
        self.in_game = False
        self.game_completed = True
        self.game_phase = 'rock_paper_scissors'
        self.my_choice = None
        self.opponent_choice = None
        self.my_direction = None
        self.opponent_direction = None
        self.waiting_for_choice = False
        self.my_turn = False
        self.game_started = False
        self.rps_winner = None
        self.rps_loser = None
        self.direction_turn_order = []
        self.my_score = 0
        self.opponent_score = 0
    
    def start_game(self):
        """開始新一輪遊戲"""
        # 檢查是否仍然連接
        if not self.connected:
            return
            
        self.my_choice = None
        self.opponent_choice = None
        self.waiting_for_choice = False
        
        # 重設兩階段遊戲狀態
        self.game_phase = 'rock_paper_scissors'
        self.rps_winner = None
        self.rps_loser = None
        self.my_direction = None
        self.opponent_direction = None
        self.direction_turn_order = []
        self.game_completed = False  # 遊戲開始，標記為進行中
        self.game_started = True  # 標記遊戲已開始
        
        # 通知對手等待
        self.send_game_message({
            'type': 'waiting_choice',
            'message': f'{self.username} 選擇中...',
            'game_phase': self.game_phase
        })
        
        print("\n🎮 新一輪開始！第一階段：猜拳")
        print("請選擇：")
        print("1 - 剪刀 ✂️")
        print("2 - 石頭 🪨")
        print("3 - 布 📄")
        print("\n💡 輸入提醒：只有看到 '{} 輸入指令:' 時才能輸入，其他時候請按 Enter 等待".format(self.username))
    

    
    def show_direction_choices(self):
        """顯示方向選擇"""
        print("方向選擇：")
        print("4 - 上 ⬆️")
        print("5 - 下 ⬇️")  
        print("6 - 左 ⬅️")
        print("7 - 右 ➡️")
        print("\n💡 輸入提醒：只有看到 '{} 輸入指令:' 時才能輸入，其他時候請按 Enter 等待".format(self.username))
    
    def handle_direction_choice(self, choice):
        """處理方向選擇"""
        direction_map = {
            '4': 'up',
            '5': 'down', 
            '6': 'left',
            '7': 'right'
        }
        
        if choice not in direction_map:
            return False
            
        direction = direction_map[choice]
        direction_emoji = {'up': '⬆️', 'down': '⬇️', 'left': '⬅️', 'right': '➡️'}
        
        self.my_direction = direction
        print(f"你選擇了：{direction_emoji[direction]}")
        
        # 發送我的方向選擇
        self.send_game_message({
            'type': 'direction_choice',
            'direction': direction,
            'player': 'player_a'
        })
        
        if self.rps_loser == 'player_a':
            # 我先選完了，通知對手選擇
            print(f"⏳ 等待 {self.opponent_name} 選擇方向...")
        else:
            # 我後選完了，等待最終結果
            if self.opponent_direction:
                self.determine_final_winner()
        
        return True
    
    def send_game_message(self, game_data):
        """發送遊戲訊息"""
        try:
            if self.opponent_socket:
                message_str = json.dumps(game_data)
                self.opponent_socket.send(message_str.encode('utf-8'))
                return True
        except Exception as e:
            print(f"Error sending game message: {e}")
        return False
    
    def determine_winner(self):
        """判斷第一階段猜拳勝負並進入第二階段"""
        choice_name = {
            'scissors': '剪刀 ✂️',
            'rock': '石頭 🪨', 
            'paper': '布 📄'
        }
        
        print(f"\n🎯 第一階段結果揭曉：")
        print(f"  你: {choice_name[self.my_choice]}")
        print(f"  {self.opponent_name}: {choice_name[self.opponent_choice]}")
        
        # 判斷猜拳勝負
        if self.my_choice == self.opponent_choice:
            #print("🤝 猜拳平手！")
            self.rps_winner = 'tie'
            self.rps_loser = None
        elif (
            (self.my_choice == 'rock' and self.opponent_choice == 'scissors') or
            (self.my_choice == 'scissors' and self.opponent_choice == 'paper') or
            (self.my_choice == 'paper' and self.opponent_choice == 'rock')
        ):
            print("🎉 你猜拳贏了！")
            self.rps_winner = 'player_a'
            self.rps_loser = 'player_b'
        else:
            print("😔 你猜拳輸了！")
            self.rps_winner = 'player_b'
            self.rps_loser = 'player_a'
        
        # 儲存選擇以便發送結果（在重設之前）
        player_a_choice = self.my_choice if self.my_choice else 'unknown'
        player_b_choice = self.opponent_choice if self.opponent_choice else 'unknown'
        
        # 重設第一階段選擇
        self.my_choice = None
        self.opponent_choice = None
        self.waiting_for_choice = False
        
        if self.rps_winner == 'tie':
            # 平手，重新開始猜拳
            print("🔄 猜拳平手，重新開始！")
            self.start_game()
        else:
            # 進入第二階段：猜方向
            print("\n" + "="*50)
            print("🎯 進入第二階段：猜方向！")
            print("規則：猜拳輸的人先選方向，猜拳贏的人後選")
            print("如果猜拳贏的人選的方向和輸的人一樣 → 猜拳贏的人獲得最終勝利")
            print("如果方向不一樣 → 平手")
            print("="*50)
            
            self.game_phase = 'direction'
        
        # 發送第一階段結果給對手，包含方向階段信息
        rps_result_data = {
            'type': 'rps_result',
            'player_a_choice': player_a_choice,
            'player_b_choice': player_b_choice,
            'rps_winner': self.rps_winner,
            'rps_loser': self.rps_loser,
            'game_phase': self.game_phase
        }
        
        # 如果進入方向階段，添加誰先選的信息
        if self.game_phase == 'direction':
            if self.rps_loser == 'player_b':
                rps_result_data['direction_first'] = 'player_b'
                rps_result_data['message'] = f'{self.opponent_name} 先選擇方向'
            else:
                rps_result_data['direction_first'] = 'player_a'
                rps_result_data['message'] = f'{self.username} 先選擇方向'
            
        self.send_game_message(rps_result_data)
        
        # 現在才啟動方向階段（不再發送額外消息）
        if self.game_phase == 'direction':
            if self.rps_loser == 'player_a':
                # 我輸了，先選方向
                self.direction_turn_order = ['player_a', 'player_b']
                print(f"\n🎯 你猜拳輸了，請先選擇方向：")
                self.show_direction_choices()
            else:
                # 我贏了，等對手先選
                self.direction_turn_order = ['player_b', 'player_a']
                print(f"\n⏳ 你猜拳贏了！等待 {self.opponent_name} 先選擇方向...")
    
    def determine_final_winner(self):
        """判斷最終勝負並給予獎勵"""
        direction_emoji = {'up': '⬆️', 'down': '⬇️', 'left': '⬅️', 'right': '➡️'}
        
        print(f"\n🏆 最終結果：")
        print(f"  你的方向: {direction_emoji[self.my_direction]}")
        print(f"  {self.opponent_name}的方向: {direction_emoji[self.opponent_direction]}")
        
        # 最終勝負判定
        if self.my_direction == self.opponent_direction:
            if self.rps_winner == 'player_a':
                # 我猜拳贏了且方向一樣 → 我最終獲勝
                print("🎉🎉 恭喜！你獲得最終勝利！")
                final_winner = 'player_a'
                self.my_score += 1
            else:
                # 對手猜拳贏了且方向一樣 → 對手最終獲勝
                print("😔 對手獲得最終勝利！")
                final_winner = 'player_b'
                self.opponent_score += 1
        else:
            # 方向不同 → 平手
            print("🤝 最終平手！")
            final_winner = 'tie'
        
        print(f"\n📊 目前比分: {self.username} {self.my_score} - {self.opponent_score} {self.opponent_name}")
        
        # 檢查是否有玩家達到3分，結束整個遊戲
        game_over = False
        if self.my_score >= 3:
            print("\n🎊 恭喜！你達到了 3 分，贏得整場遊戲！")
            print("🏆 你獲得晉級獎勵！")
            # 獲勝者晉級獎勵：500 XP (足夠升一級)
            self.update_lobby_stats({'experience_points': 500})
            print("⭐ 獲得 500 經驗值 (晉級獎勵)！")
            game_over = True
        elif self.opponent_score >= 3:
            print("\n😔 對手達到了 3 分，贏得整場遊戲！")
            # 失敗者參與獎勵：100 XP
            self.update_lobby_stats({'experience_points': -100})
            print("⭐ 失去 100 經驗值 (參與獎勵)！")
            game_over = True
        
        if not game_over:
            # 單輪獎勵
            if final_winner == 'player_a':
                # 贏家獎勵
                self.update_lobby_stats({'in_game_currency': 10, 'experience_points': 50})
                print("💰 你獲得了 10 枚遊戲幣！")
                print("⭐ 你獲得了 50 經驗值！")
            elif final_winner == 'player_b':
                # 輸家獎勵  
                self.update_lobby_stats({'in_game_currency': -10, 'experience_points': 20})
                print("💸 你失去了 10 枚遊戲幣")
                print("⭐ 你獲得了 20 參與經驗值！")
            else:  # tie
                # 平手獎勵
                self.update_lobby_stats({'in_game_currency': 0, 'experience_points': 30})
                print("⭐ 平手！你獲得了 30 經驗值！")
        
        # 發送最終結果給對手（包含是否遊戲結束的信息）
        final_result_data = {
            'type': 'final_game_result',
            'player_a_direction': self.my_direction,
            'player_b_direction': self.opponent_direction,
            'final_winner': final_winner,
            'player_a_score': self.my_score,
            'player_b_score': self.opponent_score,
            'rps_winner': self.rps_winner,
            'game_over': game_over
        }
        self.send_game_message(final_result_data)
        
        # 如果遊戲結束，強制退出
        if game_over:
            print("\n🏁 遊戲結束！感謝參與！")
            print("程序將在 3 秒後自動退出...")
            import time
            time.sleep(3)
            self.end_connection()
            return
        
        # 重設遊戲狀態
        self.reset_game_state()
        print("\n按 Enter 繼續下一輪，或輸入 'quit' 離開遊戲")
        print(f"💡 {self.username} 輸入指令: 現在可以輸入 Enter 或 quit")
    
    def reset_game_state(self):
        """重設遊戲狀態"""
        self.my_choice = None
        self.opponent_choice = None
        self.waiting_for_choice = False
        self.game_phase = 'rock_paper_scissors'
        self.rps_winner = None
        self.rps_loser = None
        self.my_direction = None
        self.opponent_direction = None
        self.direction_turn_order = []
        self.game_completed = True  # 標記遊戲完成
        self.game_started = False  # 標記遊戲未開始
    
    def start_lobby_monitor(self):
        """啟動 lobby 連接監控線程"""
        if not self.lobby_monitor_thread:
            self.lobby_monitor_thread = threading.Thread(target=self.monitor_lobby_connection, daemon=True)
            self.lobby_monitor_thread.start()
    
    def monitor_lobby_connection(self):
        """監控 lobby 伺服器連接狀態"""
        try:
            while self.logged_in and self.lobby_socket:
                try:
                    # 每 5 秒發送一個心跳檢查
                    time.sleep(5)
                    
                    if not self.lobby_socket or not self.logged_in:
                        break
                    
                    # 發送心跳包
                    heartbeat = {'action': 'heartbeat'}
                    self.lobby_socket.settimeout(3.0)  # 3秒超時
                    self.lobby_socket.send(json.dumps(heartbeat).encode('utf-8'))
                    
                    # 嘗試接收回應
                    response_data = self.lobby_socket.recv(1024).decode('utf-8')
                    if not response_data:
                        raise ConnectionError("Lobby server disconnected")
                    
                    response = json.loads(response_data)
                    if response.get('status') != 'success':
                        raise ConnectionError("Heartbeat failed")
                        
                except (socket.timeout, ConnectionError, json.JSONDecodeError, Exception) as e:
                    print(f"\n❌ Lobby 伺服器連接中斷！程序將自動退出...")
                    print(f"原因: {e}")
                    self.handle_lobby_disconnect()
                    break
                    
        except Exception as e:
            print(f"Lobby 監控線程錯誤: {e}")
            self.handle_lobby_disconnect()
    
    def handle_lobby_disconnect(self):
        """處理 lobby 斷線"""
        self.logged_in = False
        
        # 結束遊戲連接
        if self.connected:
            self.end_connection()
        
        # 清理資源
        if self.lobby_socket:
            try:
                self.lobby_socket.close()
            except:
                pass
            self.lobby_socket = None
        
        # 強制退出程序
        print("🚪 因為 Lobby 伺服器斷線，程序即將退出...")
        import sys
        import os
        os._exit(1)  # 強制退出，不執行 cleanup
    
    def update_lobby_stats(self, stats):
        """Update user statistics on lobby server"""
        if self.lobby_socket and self.logged_in:
            try:
                update_request = {
                    'action': 'update_stats',
                    'stats': stats
                }
                
                self.lobby_socket.settimeout(5.0)  # 5秒超時
                self.lobby_socket.send(json.dumps(update_request).encode('utf-8'))
                response_data = self.lobby_socket.recv(1024).decode('utf-8')
                response = json.loads(response_data)
                
                if response['status'] == 'success':
                    print("✓ Stats updated on lobby server")
                    if 'user_data' in response:
                        user_data = response['user_data']
                        print(f"  Level: {user_data['level']}, XP: {user_data['experience_points']}, 遊戲幣: {user_data['in_game_currency']}")
                else:
                    print(f"Stats update failed: {response['message']}")
            
            except (socket.timeout, ConnectionError, json.JSONDecodeError) as e:
                print(f"❌ Lobby 連接問題，無法更新統計: {e}")
                self.handle_lobby_disconnect()
            except Exception as e:
                print(f"Error updating stats: {e}")
    
    def show_level_info(self):
        """显示等級和升級進度資訊"""
        if not (self.lobby_socket and self.logged_in):
            print("❌ 未連接到大廳伺服器")
            return
            
        try:
            # 獲取當前用戶資訊
            info_request = {'action': 'get_user_info'}
            self.lobby_socket.send(json.dumps(info_request).encode('utf-8'))
            response_data = self.lobby_socket.recv(1024).decode('utf-8')
            response = json.loads(response_data)
            
            if response['status'] == 'success':
                user_data = response['user_data']
                current_level = user_data['level']
                current_xp = user_data['experience_points']
                
                # 計算當前等級的 XP 範圍 (每 500 XP 一級)
                level_start_xp = (current_level - 1) * 500
                level_end_xp = current_level * 500
                level_progress_xp = current_xp - level_start_xp
                next_level_need_xp = level_end_xp - current_xp
                
                print(f"🎆 等級資訊")
                print(f"目前等級: {current_level}")
                print(f"總經驗值: {current_xp} XP")
                print(f"💰 遊戲幣: {user_data['in_game_currency']} 幣")
                print(f"本等級進度: {level_progress_xp}/500 XP")
                if next_level_need_xp > 0:
                    progress_percentage = (level_progress_xp * 100) // 500
                    progress_bar = "█" * (progress_percentage // 10) + "░" * (10 - progress_percentage // 10)
                    print(f"進度條: [{progress_bar}] {progress_percentage}%")
                    print(f"升下一級還需: {next_level_need_xp} XP")
                else:
                    print(f"恭喜！你已經満級了！")
                    
                print(f"🎮 獎勵方式 (每 500 XP 一級):")
                print(f"• 登入: +50 XP")
                print(f"• 遊戲勝利: +50 XP")
                print(f"• 遊戲失敗: +20 XP")
                print(f"• 遊戲平手: +30 XP")
                
            else:
                print(f"❌ 獲取等級資訊失敗: {response['message']}")
                
        except (socket.timeout, ConnectionError, json.JSONDecodeError) as e:
            print(f"❤️ Lobby 連接問題，無法獲取等級資訊: {e}")
            self.handle_lobby_disconnect()
        except Exception as e:
            print(f"獲取等級資訊時發生錯誤: {e}")
    
    def exchange_xp_for_currency(self):
        """兌換經驗值為遊戲幣"""
        if not (self.lobby_socket and self.logged_in):
            print("❌ 未連接到大廳伺服器")
            return
            
        try:
            # 先獲取當前用戶資訊
            info_request = {'action': 'get_user_info'}
            self.lobby_socket.settimeout(5.0)  # 5秒超時
            self.lobby_socket.send(json.dumps(info_request).encode('utf-8'))
            response_data = self.lobby_socket.recv(1024).decode('utf-8')
            response = json.loads(response_data)
            
            if response['status'] == 'success':
                user_data = response['user_data']
                current_xp = user_data['experience_points']
                current_currency = user_data['in_game_currency']
                
                max_exchange = current_xp // 10
                if max_exchange <= 0:
                    print(f"❌ 經驗值不足！目前 XP: {current_xp}，需要至少 10 XP 才能兌換")
                    return
                
                print(f"💰 經驗值兌換遊戲幣")
                print(f"目前 XP: {current_xp}，遊戲幣: {current_currency}")
                print(f"最多可兌換: {max_exchange} 枚遊戲幣 (消耗 {max_exchange * 10} XP)")
                
                try:
                    exchange_amount = int(input("請輸入要兌換的遊戲幣數量: ").strip())
                    
                    if exchange_amount <= 0:
                        print("❌ 兌換數量必須大於 0")
                        return
                    elif exchange_amount > max_exchange:
                        print(f"❌ 兌換數量超過限制！最多可兌換 {max_exchange} 枚")
                        return
                    
                    # 執行兌換
                    exchange_stats = {
                        'experience_points': -exchange_amount * 10,
                        'in_game_currency': exchange_amount
                    }
                    
                    self.update_lobby_stats(exchange_stats)
                    print(f"✓ 成功兌換 {exchange_amount} 枚遊戲幣！消耗了 {exchange_amount * 10} XP")
                    
                except ValueError:
                    print("❌ 請輸入有效的數字")
                except (KeyboardInterrupt, EOFError):
                    print("\n取消兌換")
            else:
                print(f"❌ 獲取用戶資訊失敗: {response['message']}")
                
        except (socket.timeout, ConnectionError, json.JSONDecodeError) as e:
            print(f"❌ Lobby 連接問題，無法進行兌換: {e}")
            self.handle_lobby_disconnect()
        except Exception as e:
            print(f"兌換過程發生錯誤: {e}")
    
    def end_connection(self, apply_penalty=True):
        """End the current connection session"""
        # 檢查遊戲狀態在重置之前
        was_in_game = self.in_game and not self.game_completed
        
        # 重置遊戲狀態
        self.connected = False
        self.reset_game_state()
        
        if self.opponent_socket:
            try:
                # 如果在遊戲期間斷線，發送quit消息讓對手獲得獎勵
                if was_in_game and apply_penalty:
                    quit_msg = {
                        'type': 'opponent_quit',
                        'message': f'{self.username} 已離開遊戲',
                        'reward_winner': True
                    }
                    self.opponent_socket.send(json.dumps(quit_msg).encode('utf-8'))
                    # 自己也要被扣分
                    print("💸 遊戲中途離開，已扣除 100 XP 作為懲罰")
                    self.update_user_stats(-100, 0)
                else:
                    # Send normal disconnect message
                    disconnect_msg = {'type': 'disconnect'}
                    self.opponent_socket.send(json.dumps(disconnect_msg).encode('utf-8'))
                self.opponent_socket.close()
            except:
                pass
            self.opponent_socket = None
        
        self.cleanup_tcp_server()
        self.opponent_name = None
        
        print("\n🏁 Connection ended.")
    
    def cleanup_tcp_server(self):
        """Clean up TCP server resources"""
        if self.tcp_socket:
            try:
                self.tcp_socket.close()
            except:
                pass
            self.tcp_socket = None
        self.tcp_port = None
    
    def run(self):
        """Main run loop for Player A"""
        print(f"Starting Player A ({self.username})...")
        
        # 如果已經登入，跳過連線流程
        if self.logged_in and self.lobby_socket:
            print("✅ 使用現有登入狀態")
        else:
            # Connect to lobby server with retry
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                if self.connect_to_lobby():
                    break
                
                retry_count += 1
                print(f"❌ 連接失敗 (嘗試 {retry_count}/{max_retries})")
            
            if retry_count < max_retries:
                print("\n請選擇操作:")
                print("1. 重新嘗試登入")
                print("2. 註冊新的帳號")
                print("3. 退出程序")
                
                while True:
                    choice = input("\n請輸入選項 (1-3): ").strip()
                    if choice == "1":
                        # 重新輸入帳號密碼，並切換為登入模式
                        print(f"\n🔐 重新輸入登入資訊")
                        self.username = input("Username: ")
                        self.password = input("Password: ")
                        self.register_mode = False  # 切換為登入模式
                        break
                    elif choice == "2":
                        # 註冊新的帳號
                        print(f"\n📝 註冊新的帳號")
                        self.username = input("新的 Username: ")
                        while True:
                            self.password = input("新的 Password: ")
                            confirm_password = input("確認 Password: ")
                            if self.password == confirm_password:
                                break
                            else:
                                print("❌ 密碼不一致，請重新輸入")
                        self.register_mode = True  # 切換為註冊模式
                        break
                    elif choice == "3":
                        print("👋 退出程序")
                        return
                    else:
                        print("❌ 無效選項，請重新輸入")
            
            if retry_count >= max_retries:
                print("❌ 多次嘗試失敗，程序退出")
                return
        
        print(f"\n🎮 玩家 {self.username} 已就緒！")
        print("Commands:")
        print("  'scan' - 掃描線上玩家")  
        print("  'invite <玩家名稱>' - 邀請特定玩家")
        print("  'list' - 顯示最後掃描結果")
        print("  'exchange' - 兌換經驗值為遊戲幣 (10XP = 1幣)")
        print("  'level' - 查看等級和升級進度") 
        print("  'quit' - 退出程序")
        print("💡 或按 Ctrl+C 退出程序")
        
        try:
            while True:
                if self.connected:
                    # Connection is active, wait for it to end
                    while self.connected:
                        time.sleep(1)
                    
                    # Game ended, return to main menu
                    print("\n🎮 回到主選單")
                    print("Commands:")
                    print("  'scan' - 掃描線上玩家")  
                    print("  'invite <玩家名稱>' - 邀請特定玩家")
                    print("  'list' - 顯示最後掃描結果")
                    print("  'quit' - 退出程序")
                    continue
                
                command_input = input("\n輸入指令: ").strip()
                command_parts = command_input.split()
                
                if not command_parts:
                    continue
                    
                command = command_parts[0].lower()
                
                if command == 'quit':
                    break
                
                elif command == 'scan':
                    # Scan for available players (just show list, don't auto-invite)
                    available_players = self.scan_for_players()
                    self.last_scan_results = available_players  # Save scan results
                    self.display_available_players(available_players)
                    
                    if available_players:
                        print(f"\n💡 使用 'invite <玩家名稱>' 來邀請玩家，例如: invite {available_players[0]['name']}")
                
                elif command == 'list':
                    # Display last scan results
                    if self.last_scan_results:
                        print("\n📋 最後掃描結果:")
                        self.display_available_players(self.last_scan_results)
                        if self.last_scan_results:
                            print(f"\n💡 使用 'invite <玩家名稱>' 來邀請玩家")
                    else:
                        print("❌ 沒有掃描結果。請先使用 'scan' 指令")
                
                elif command == 'invite':
                    # Invite specific player by name
                    if len(command_parts) < 2:
                        print("❌ 請指定要邀請的玩家名稱，例如: invite alice")
                        continue
                    
                    target_name = command_parts[1]
                    
                    # Find player in last scan results
                    target_player = None
                    for player in self.last_scan_results:
                        if player['name'].lower() == target_name.lower():
                            target_player = player
                            break
                    
                    if target_player:
                        print(f"📨 正在邀請 {target_player['name']}...")
                        if self.send_invitation(target_player):
                            # Game will start automatically if accepted
                            pass
                        else:
                            print("❌ 邀請失敗，請檢查玩家是否仍然在線")
                    else:
                        print(f"❌ 找不到玩家 '{target_name}'")
                        if self.last_scan_results:
                            print("可用玩家:")
                            for player in self.last_scan_results:
                                print(f"  • {player['name']}")
                        else:
                            print("請先使用 'scan' 指令掃描可用玩家")
                
                elif command == 'exchange':
                    self.exchange_xp_for_currency()
                    
                elif command == 'level':
                    self.show_level_info()
                
                else:
                    print("❌ 未知指令。可用指令: scan, invite <玩家名稱>, list, exchange, level, quit")
        
        except KeyboardInterrupt:
            print(f"\n正在關閉 {self.username} 的遊戲...")
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up all resources"""
        self.end_connection()
        
        # 停止 lobby 監控
        self.logged_in = False
        
        if self.udp_socket:
            self.udp_socket.close()
        
        if self.lobby_socket:
            try:
                # Send logout message
                logout_request = {'action': 'logout'}
                self.lobby_socket.send(json.dumps(logout_request).encode('utf-8'))
                self.lobby_socket.close()
            except:
                pass
        
        print(f"玩家 {self.username} 已離線。")


class PlayerB:
    def __init__(self, username, password, lobby_host=None, lobby_port=12000, 
                 udp_port=10000, register_mode=False):
        self.username = username
        self.password = password
        self.register_mode = register_mode
        
        # Lobby server connection - 自動檢測或使用預設
        if lobby_host is None:
            self.lobby_host = self.detect_lobby_server()
        else:
            self.lobby_host = lobby_host
        self.lobby_port = lobby_port
        self.lobby_socket = None
        self.logged_in = False
        
        # UDP listener for invitations
        self.udp_port = udp_port
        self.udp_socket = None
        self.listening = False
        
        # Connection session
        self.connected = False
        self.connection_socket = None
        self.opponent_name = None
        
        # Threading
        self.udp_thread = None
        self.connection_thread = None
        self.lobby_monitor_thread = None
        
        # Invitation handling
        self.pending_invitation = None
        self.has_pending_invitation = False
        
        # Input prompt management
        self.prompt_shown = False
        
        # Game state
        self.in_game = False
        self.my_choice = None
        self.opponent_choice = None
        self.my_score = 0
        self.opponent_score = 0
        self.waiting_for_opponent = False
        self.my_turn = False
        
        # Two-phase game state
        self.game_phase = 'rock_paper_scissors'  # 'rock_paper_scissors' or 'direction'
        self.rps_winner = None  # 'player_a', 'player_b', or 'tie'
        self.rps_loser = None   # 'player_a', 'player_b', or None
        self.my_direction = None
        self.opponent_direction = None
        self.direction_turn_order = []  # [first_chooser, second_chooser]
        self.game_completed = True  # 遊戲是否完成，可以開始新一輪
        
        # Penalty control for connection termination
        self.should_apply_penalty_on_exit = True
        
        # Auto-disconnect timer (60 seconds without invitation)
        self.start_time = None
        self.timeout_seconds = 60
        self.timeout_thread = None
    
    def detect_lobby_server(self):
        """自動檢測 lobby server 位置"""
        try:
            import socket
            
            # 方法1: 檢查是否在 NYCU 網域內
            hostname = socket.gethostname()
            print(f"🔍 檢測到主機名: {hostname}")
            
            if 'linux' in hostname and 'cs.nycu.edu.tw' in hostname:
                lobby_ip = '127.0.0.1'
                print(f"🏫 檢測到 NYCU 環境，使用 lobby server: {lobby_ip}")
                return lobby_ip
            
            # 方法2: 嘗試連接各個可能的 lobby server
            potential_servers = [
                '140.113.235.151',  # linux1
                '140.113.235.152',  # linux2
                '140.113.235.153',  # linux3  
                '140.113.235.154',  # linux4
                '127.0.0.1'         # localhost
            ]
            
            for server_ip in potential_servers:
                try:
                    # 快速檢測端口是否開放
                    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    test_socket.settimeout(1.0)  # 1秒超時
                    result = test_socket.connect_ex((server_ip, self.lobby_port))
                    test_socket.close()
                    
                    if result == 0:  # 連接成功
                        print(f"✅ 找到可用的 lobby server: {server_ip}")
                        return server_ip
                        
                except:
                    continue
            
            # 方法3: 預設值
            default_ip = '127.0.0.1'
            print(f"⚠️ 無法自動檢測 lobby server，使用預設: {default_ip}")
            return default_ip
            
        except Exception as e:
            print(f"❌ Lobby server 檢測失敗: {e}")
            return '127.0.0.1'  # 預設值
        
    def connect_to_lobby(self):
        """Connect and login to the lobby server"""
        try:
            print(f"🔗 正在連接到 lobby server: {self.lobby_host}:{self.lobby_port}")
            self.lobby_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.lobby_socket.connect((self.lobby_host, self.lobby_port))
            
            if self.register_mode:
                # 註冊模式 - 先嘗試註冊
                print(f"📝 正在註冊新帳號 '{self.username}'...")
                register_request = {
                    'action': 'register',
                    'username': self.username,
                    'password': self.password
                }
                
                self.lobby_socket.send(json.dumps(register_request).encode('utf-8'))
                response_data = self.lobby_socket.recv(1024).decode('utf-8')
                response = json.loads(response_data)
                
                if response['status'] == 'success':
                    print(f"✓ 註冊成功！歡迎 {self.username}")
                    # 註冊成功後自動登入
                    self.register_mode = False  # 避免遞迴呼叫
                    return self.connect_to_lobby()
                else:
                    print(f"✗ 註冊失敗: {response['message']}")
                    return False
            else:
                # 登入模式
                print(f"🔐 正在登入帳號 '{self.username}'...")
                login_request = {
                    'action': 'login',
                    'username': self.username,
                    'password': self.password
                }
                
                self.lobby_socket.send(json.dumps(login_request).encode('utf-8'))
                response_data = self.lobby_socket.recv(1024).decode('utf-8')
                response = json.loads(response_data)
                
                if response['status'] == 'success':
                    print(f"✓ 登入成功！歡迎回來 {self.username}")
                    if 'user_data' in response:
                        user_data = response['user_data']
                        print(f"  等級: {user_data['level']}, 經驗值: {user_data['experience_points']} XP")
                        print(f"  遊戲幣: {user_data['in_game_currency']}, 登入次數: {user_data['login_count']}")
                    self.logged_in = True
                    
                    # 啟動 lobby 連線監控
                    self.start_lobby_monitor()
                    return True
                else:
                    print(f"✗ 登入失敗: {response['message']}")
                    return False
                
        except Exception as e:
            print(f"✗ Error connecting to lobby server: {e}")
            return False
    
    def find_available_udp_port(self, start_port=10000, max_attempts=200):
        """Find an available UDP port starting from start_port"""
        for port_offset in range(max_attempts):
            test_port = start_port + port_offset
            try:
                # Test if port is available by binding to the same interface we'll actually use
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                test_socket.bind(('127.0.0.1', test_port))  # 綁定到本機接口
                test_socket.close()
                
                # Double check by trying to bind again immediately
                verify_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                verify_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                verify_socket.bind(('127.0.0.1', test_port))
                verify_socket.close()
                
                print(f"🔍 找到可用UDP端口: {test_port}")
                return test_port
            except OSError as e:
                if port_offset < 3:  # 只在前幾次顯示詳細錯誤
                    print(f"⚠️ 端口 {test_port} 已被佔用，重新尋找...")
                continue
        return None
    
    def start_udp_listener(self):
        """Start listening for UDP invitations"""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to the already selected available port
            bind_success = False
            retry_count = 0
            max_retries = 3
            
            while not bind_success and retry_count < max_retries:
                try:
                    if self.udp_port == 0:
                        # Let system automatically assign an available port
                        self.udp_socket.bind(('127.0.0.1', 0))
                        # Get the actually assigned port
                        self.udp_port = self.udp_socket.getsockname()[1]
                        print(f"✓ 系統自動分配端口: {self.udp_port}")
                    else:
                        self.udp_socket.bind(('127.0.0.1', self.udp_port))
                        print(f"✓ UDP監聽器綁定到 127.0.0.1:{self.udp_port}")
                    bind_success = True
                except OSError as e:
                    retry_count += 1
                    print(f"⚠️ 端口 {self.udp_port} 綁定失敗 (嘗試 {retry_count}/{max_retries}): {e}")
                    
                    if retry_count < max_retries:
                        if self.udp_port == 0:
                            # If system auto-assign failed, try manual search
                            new_port = self.find_available_udp_port(10000)
                            if new_port:
                                self.udp_port = new_port
                                print(f"🔄 改用手動搜尋端口: {self.udp_port}")
                            else:
                                print("❌ 無法找到可用端口")
                                break
                        else:
                            # Try to find a new port
                            new_port = self.find_available_udp_port(self.udp_port + 1)
                            if new_port:
                                self.udp_port = new_port
                                print(f"🔄 嘗試新端口: {self.udp_port}")
                            else:
                                print("❌ 無法找到更多可用端口")
                                break
            
            if not bind_success:
                raise Exception(f"無法綁定UDP端口，已嘗試 {max_retries} 次")
            
            self.listening = True
            print(f"✓ 開始監聽遊戲邀請 (UDP 端口 {self.udp_port})")
            
            self.udp_socket.settimeout(1.0)  # Set timeout for clean shutdown
            
            while self.listening and not self.connected:
                try:
                    data, address = self.udp_socket.recvfrom(1024)
                    message_str = data.decode('utf-8')
                    
                    try:
                        message = json.loads(message_str)
                        self.handle_udp_message(message, address)
                    except json.JSONDecodeError:
                        print(f"Received invalid JSON from {address}")
                
                except socket.timeout:
                    continue
                except KeyboardInterrupt:
                    print(f"\n⚠️ 收到中斷信號，停止UDP監聽...")
                    self.listening = False
                    break
                except Exception as e:
                    if self.listening:
                        print(f"UDP listener error: {e}")
                    break
        
        except Exception as e:
            print(f"✗ Error starting UDP listener: {e}")
        
        finally:
            if self.udp_socket:
                self.udp_socket.close()
    
    def handle_udp_message(self, message, address):
        """Handle incoming UDP messages"""
        msg_type = message.get('type')
        
        if msg_type == 'scan':
            # Respond to player scan (silent response, no user notification)
            response = {
                'type': 'scan_response',
                'player': self.username,
                'status': 'available' if not self.connected else 'busy',
                'port': self.udp_port
            }
            
            try:
                self.udp_socket.sendto(
                    json.dumps(response).encode('utf-8'), 
                    address
                )
                # 不打印訊息，靜默回應掃描
            except Exception as e:
                print(f"Error responding to scan: {e}")
        
        elif msg_type == 'invitation':
            # Handle game invitation
            inviter = message.get('from_player')
            game_type = message.get('game_type', 'tic-tac-toe')
            
            print(f"\n🎮 Game invitation received!")
            print(f"From: {inviter}")
            print(f"Game: {game_type}")
            
            # Reset timeout timer when invitation is received
            self.reset_timeout_timer()
            
            # Store invitation details for processing
            self.pending_invitation = {
                'inviter': inviter,
                'address': address,
                'game_type': game_type
            }
            
            # Set flag to handle invitation in main loop
            self.has_pending_invitation = True
            
            print(f"Accept invitation? (y/n): ", end='', flush=True)
        
        elif msg_type == 'tcp_connection':
            # Handle TCP connection information from Player A
            self.handle_connection_info(message, address)
    
    def accept_invitation(self, inviter, address):
        """Accept a game invitation"""
        try:
            response = {
                'type': 'invitation_response',
                'accepted': True,
                'player': self.username
            }
            
            self.udp_socket.sendto(
                json.dumps(response).encode('utf-8'), 
                address
            )
            
            print(f"✓ Accepted invitation from {inviter}")
            print("Waiting for game connection details...")
            
        except Exception as e:
            print(f"Error accepting invitation: {e}")
    
    def decline_invitation(self, inviter, address):
        """Decline a game invitation"""
        try:
            response = {
                'type': 'invitation_response',
                'accepted': False,
                'player': self.username
            }
            
            self.udp_socket.sendto(
                json.dumps(response).encode('utf-8'), 
                address
            )
            
            print(f"Declined invitation from {inviter}")
            
        except Exception as e:
            print(f"Error declining invitation: {e}")
    
    def handle_connection_info(self, message, address):
        """Handle TCP connection info from Player A"""
        tcp_host = message.get('tcp_host')
        tcp_port = message.get('tcp_port')
        
        if tcp_host and tcp_port:
            print(f"Received game connection: {tcp_host}:{tcp_port}")
            self.connect_to_game(tcp_host, tcp_port)
        else:
            print("Invalid connection info received")
    
    def connect_to_game(self, host, port):
        """Connect to the TCP game server"""
        try:
            self.connection_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connection_socket.connect((host, port))
            
            print(f"✓ Connected to game server at {host}:{port}")
            
            # Send handshake
            handshake = {
                'type': 'handshake',
                'player_name': self.username
            }
            self.connection_socket.send(json.dumps(handshake).encode('utf-8'))
            
            # Wait for handshake response
            self.connection_socket.settimeout(10.0)
            response_data = self.connection_socket.recv(1024).decode('utf-8')
            
            if response_data:
                try:
                    response = json.loads(response_data)
                    if response.get('type') == 'handshake_response':
                        self.opponent_name = response.get('player_name', 'Unknown')
                        print(f"✓ 握手成功，對手: {self.opponent_name}")
                        
                        self.connected = True
                        
                        # Stop UDP listener and timeout timer
                        self.listening = False
                        
                        # Start connection session
                        self.connection_thread = threading.Thread(target=self.connection_session, daemon=True)
                        self.connection_thread.start()
                        return
                except json.JSONDecodeError:
                    pass
            
            print("❌ 握手失敗")
            self.connection_socket.close()
            
        except Exception as e:
            print(f"✗ Error connecting: {e}")
            self.connected = False
    
    def connection_session(self):
        """Handle the TCP connection session"""
        print("\n✓ 連線建立成功!")
        print(f"📍 你是 {self.username}")
        print(f"🤝 對手: {self.opponent_name}")
        print("=" * 50)
        print("連線已建立，正在等待遊戲開始！")
        print("⚠️ 等待中，請不要輸入任何內容，只需按 Enter 等待！")
        print("=" * 50)
        print("🎮 兩階段遊戲：猜拳 + 猜方向")
        print("🎯 規則說明：")
        print("  • 第一階段：猜拳 (剪刀石頭布)")
        print("  • 第二階段：猜方向 (上下左右)")
        print("  • 猜拳輸的人先選方向，贏的人後選")
        print("  • 如果猜拳贏的人選的方向和輸的人一樣 → 猜拳贏的人最終獲勝")
        print("  • 如果方向不一樣 → 平手")
        print("💡 第一階段指令:")
        print("  • 1 - 剪刀 ✂️")
        print("  • 2 - 石頭 🪨")
        print("  • 3 - 布 📄")
        print("💡 第二階段指令:")
        print("  • 4 - 上 ⬆️")
        print("  • 5 - 下 ⬇️")
        print("  • 6 - 左 ⬅️")
        print("  • 7 - 右 ➡️")
        print("  • quit - 離開遊戲")
        print("=" * 50)
        print("\n⚠️ 重要提醒：只有看到 '{} 輸入指令:' 時才能輸入指令！".format(self.username))
        print("其他時候（等待對方、顯示結果等）請按 Enter 鍵等待，不要隨意輸入！")
        print("=" * 50)
        
        self.in_game = True
        self.should_apply_penalty_on_exit = True  # 默認應該應用懲罰
        
        try:
            # Main connection loop
            while self.connected:
                # Check for incoming messages first
                self.connection_socket.settimeout(0.1)
                try:
                    data = self.connection_socket.recv(1024).decode('utf-8')
                    if not data:
                        print("🔌 對手已斷線")
                        # 如果在遊戲進行中，給自己獎勵
                        if self.in_game and not self.game_completed:
                            print("🎉 對手中途斷線，你獲得了 100 經驗值獎勵！")
                            self.update_user_stats(100, 0)
                        self.should_apply_penalty_on_exit = False  # 對手斷線時不懲罰自己
                        break
                    
                    # 處理可能連在一起的多個JSON消息
                    self.process_received_data(data)
                    
                except json.JSONDecodeError:
                    print(f"收到無效訊息: {data}")
                
                except socket.timeout:
                    # No message received, check for input
                    if self.connected:
                        if not self.prompt_shown:
                            print(f"{self.username} 輸入指令: ", end='', flush=True)
                            self.prompt_shown = True
                        self.handle_connection_input()
                    continue
                except Exception as e:
                    print(f"Error receiving message: {e}")
                    continue
        
        except KeyboardInterrupt:
            print(f"\n⚠️ 收到中斷信號，正在結束遊戲連接...")
            # 通知對手離開
            if self.in_game:
                self.handle_quit_in_game()
        except Exception as e:
            print(f"Connection session error: {e}")
        
        finally:
            self.end_connection_session(apply_penalty=self.should_apply_penalty_on_exit)
    
    def send_message(self, message_text):
        """Send simple text message to opponent via TCP"""
        try:
            if self.connection_socket and self.connected:
                message = {
                    'type': 'message',
                    'content': message_text,
                    'from': self.username
                }
                message_str = json.dumps(message)
                self.connection_socket.send(message_str.encode('utf-8'))
                print(f"→ 傳送: {message_text}")
                return True
            return False
        except Exception as e:
            print(f"Error sending message: {e}")
            return False
    
    def handle_opponent_message(self, message):
        """Handle incoming messages from opponent"""
        msg_type = message.get('type')
        
        if msg_type == 'message':
            content = message.get('content', '')
            from_user = message.get('from', 'Unknown')
            print(f"← {from_user}: {content}")
        
        elif msg_type == 'system':
            content = message.get('content', '')
            print(f"🔔 系統: {content}")
        
        elif msg_type == 'opponent_quit':
            quit_message = message.get('message', '對手已離開遊戲')
            print(f"⚠️ {quit_message}")
            
            # 檢查是否有獲勝獎勵
            reward_winner = message.get('reward_winner', False)
            if reward_winner:
                try:
                    # 更新經驗值 +100
                    update_response = self.lobby_client.send_request({
                        "action": "update_player_stats",
                        "username": self.username,
                        "wins": 1,
                        "xp": 100
                    })
                    if update_response and update_response.get('success'):
                        print("🎉 對手中途退出，你獲得了 100 經驗值獎勵！")
                    else:
                        print("⚠️ 更新獎勵經驗值失敗")
                except Exception as e:
                    print(f"⚠️ 更新經驗值時發生錯誤: {e}")
            
            # 完全重置遊戲狀態
            self.reset_game_state()
            self.should_apply_penalty_on_exit = False  # 對手離開時不懲罰自己
            print("🚪 遊戲結束，正在退出...")
            self.connected = False
            return
        
        elif msg_type == 'disconnect':
            print("⚠️ 對手已斷線，遊戲結束")
            # 如果在遊戲進行中，給自己獎勵
            if self.in_game and not self.game_completed:
                print("🎉 對手中途斷線，你獲得了 100 經驗值獎勵！")
                self.update_user_stats(100, 0)
            
            # 完全重置遊戲狀態
            self.reset_game_state()
            self.should_apply_penalty_on_exit = False  # 對手斷線時不懲罰自己
            self.connected = False
            return
        
        else:
            print(f"收到未知訊息類型: {msg_type}")
    
    def process_received_data(self, data):
        """處理接收到的數據，可能包含多個JSON消息"""
        # 嘗試分割可能連在一起的JSON消息
        messages = []
        buffer = data
        
        while buffer:
            try:
                # 嘗試解析JSON
                message, idx = json.JSONDecoder().raw_decode(buffer)
                messages.append(message)
                buffer = buffer[idx:].strip()
            except json.JSONDecodeError:
                # 如果無法解析，嘗試找到下一個'{'
                start_idx = buffer.find('{', 1)
                if start_idx != -1:
                    # 嘗試解析第一部分
                    try:
                        first_part = buffer[:start_idx]
                        message = json.loads(first_part)
                        messages.append(message)
                        buffer = buffer[start_idx:]
                    except json.JSONDecodeError:
                        print(f"收到無效訊息: {data}")
                        break
                else:
                    print(f"收到無效訊息: {data}")
                    break
        
        # 處理所有解析成功的消息
        for message in messages:
            self.handle_connection_message(message)

    def handle_connection_message(self, message):
        """Handle incoming connection messages"""
        msg_type = message.get('type')
        
        if msg_type == 'player_choice':
            if self.game_phase == 'rock_paper_scissors':
                # Player A 的猜拳選擇
                self.opponent_choice = message.get('choice')
        
        elif msg_type == 'waiting_choice':
            # player_a 選擇中，player_b 只是等待，不輪到自己
            phase = message.get('game_phase', 'rock_paper_scissors')
            self.waiting_for_opponent = True
            self.game_completed = False  # 遊戲開始，標記為進行中
            
            # 如果是重新開始猜拳階段，重置相關狀態
            if phase == 'rock_paper_scissors':
                self.game_phase = 'rock_paper_scissors'
                self.my_choice = None
                self.opponent_choice = None
                self.my_turn = False
                self.rps_winner = None
                self.rps_loser = None
                self.my_direction = None
                self.opponent_direction = None
                self.direction_turn_order = []
                print(f"{self.opponent_name} 選擇中...")
            elif phase == 'direction':
                print(f"{self.opponent_name} 選擇方向中...")
        
        elif msg_type == 'your_turn':
            # 輪到 player_b 選擇猜拳
            if self.game_phase == 'rock_paper_scissors':
                self.my_turn = True
                self.show_choice_prompt()
        
        elif msg_type == 'rps_result':
            # 收到猜拳結果，進入方向階段
            self.handle_rps_result(message)
        

        
        elif msg_type == 'direction_choice':
            # 收到對手的方向選擇
            self.handle_opponent_direction_choice(message)
        
        elif msg_type == 'final_game_result':
            # 收到最終遊戲結果
            self.handle_final_game_result(message)
        
        else:
            self.handle_opponent_message(message)
    
    def handle_quit_in_game(self):
        """處理遊戲中途退出的邏輯"""
        # 檢查是否在遊戲進行中（已開始但未結束）
        if self.in_game and not self.game_completed:
            print("⚠️ 遊戲進行中離開將被扣除 100 XP!")
            
            # 通知對手玩家退出並獲得獎勵
            self.send_game_message({
                'type': 'opponent_quit',
                'message': f'{self.username} 已離開遊戲',
                'reward_winner': True  # 告知對手可獲得獎勵
            })
            
            # 扣除經驗值
            self.update_user_stats(-100, 0)
            print("💸 已扣除 100 XP 作為懲罰")
            print(f"🎁 對手 {self.opponent_name} 將獲得 100 XP 獎勵")
            
            print("🚪 離開遊戲...")
        else:
            print("🚪 離開遊戲...")
        
        self.connected = False
    
    def update_user_stats(self, exp_change, currency_change):
        """更新用戶統計（經驗值和遊戲幣）"""
        stats = {}
        if exp_change != 0:
            stats['experience_points'] = exp_change
        if currency_change != 0:
            stats['in_game_currency'] = currency_change
        
        if stats:
            self.update_lobby_stats(stats)
    
    def reset_game_state(self):
        """重置所有遊戲狀態變量"""
        self.in_game = False
        self.game_completed = True
        self.game_phase = 'rock_paper_scissors'
        self.my_choice = None
        self.opponent_choice = None
        self.my_direction = None
        self.opponent_direction = None
        self.waiting_for_choice = False
        self.my_turn = False
        self.game_started = False
        self.rps_winner = None
        self.rps_loser = None
        self.direction_turn_order = []
        self.my_score = 0
        self.opponent_score = 0
    
    def handle_connection_input(self):
        """Handle user input during connection"""
        try:
            import sys
            import select
            
            # Non-blocking input check
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                user_input = input().strip()
                self.prompt_shown = False
                
                if not user_input:
                    # 空輸入 (Enter) - 顯示當前狀態提示
                    if self.game_phase == 'rock_paper_scissors':
                        if self.my_turn and not self.my_choice:
                            print("🎯 請選擇你的猜拳：")
                            self.show_choice_prompt()
                        elif not self.my_turn:
                            print("⏳ 等待輪到你...")
                    elif self.game_phase == 'direction':
                        if not self.my_direction:
                            # 使用與輸入處理相同的邏輯檢查是否輪到我選擇
                            can_choose = False
                            
                            if self.direction_turn_order and self.direction_turn_order[0] == 'player_b':
                                # 我是第一個選擇的
                                can_choose = True
                            elif (self.rps_winner == 'player_b' and self.opponent_direction):
                                # 我猜拳贏了，對手先選完了，現在輪到我
                                can_choose = True
                            elif (self.direction_turn_order and len(self.direction_turn_order) > 1 and 
                                  self.direction_turn_order[1] == 'player_b' and self.opponent_direction):
                                # 按照輪次順序，我是第二個，且對手已選擇
                                can_choose = True
                            
                            if can_choose:
                                print("🎯 現在輪到你選擇方向：")
                                self.show_direction_choices()
                            else:
                                if not self.opponent_direction:
                                    print(f"⏳ 等待 {self.opponent_name} 先選擇方向...")
                                else:
                                    print("❌ 現在不是你選擇方向的時候")
                        else:
                            if not self.opponent_direction:
                                print(f"⏳ 等待 {self.opponent_name} 選擇方向...")
                            else:
                                print("⏳ 等待最終結果...")
                    return
                    
                command_parts = user_input.split()
                command = command_parts[0].lower()
                
                if command == 'quit':
                    self.handle_quit_in_game()
                    return
                    
                elif command in ['1', '2', '3', '4', '5', '6', '7']:
                    if self.game_phase == 'rock_paper_scissors':
                        # 第一階段：猜拳
                        if command in ['1', '2', '3']:
                            if self.my_turn and not self.my_choice:
                                choice_map = {'1': 'scissors', '2': 'rock', '3': 'paper'}
                                choice_emoji = {'1': '✂️', '2': '🪨', '3': '📄'}
                                choice_name = {'1': '剪刀', '2': '石頭', '3': '布'}
                                
                                self.my_choice = choice_map[command]
                                print(f"你選擇了: {choice_name[command]} {choice_emoji[command]}")
                                
                                # 發送選擇給對手
                                self.send_game_message({
                                    'type': 'player_choice',
                                    'choice': self.my_choice,
                                    'player': self.username
                                })
                                
                                self.my_turn = False
                                print("等待結果中...")
                            elif not self.my_turn:
                                print("請等待輪到你")
                            else:
                                print("你已經選擇過了")
                        elif command in ['4', '5', '6', '7']:
                            print("❌ 現在是猜拳階段，請選擇 1-3")
                    
                    elif self.game_phase == 'direction':
                        # 第二階段：猜方向
                        if command in ['4', '5', '6', '7']:
                            # 檢查是否輪到我選擇方向
                            if not self.my_direction:
                                # 檢查是否輪到我選擇
                                can_choose = False
                                
                                if self.direction_turn_order and self.direction_turn_order[0] == 'player_b':
                                    # 我是第一個選擇的
                                    can_choose = True
                                elif (self.rps_winner == 'player_b' and self.opponent_direction):
                                    # 我猜拳贏了，對手先選完了，現在輪到我
                                    can_choose = True
                                elif (self.direction_turn_order and len(self.direction_turn_order) > 1 and 
                                      self.direction_turn_order[1] == 'player_b' and self.opponent_direction):
                                    # 按照輪次順序，我是第二個，且對手已選擇
                                    can_choose = True
                                
                                if can_choose:
                                    self.handle_direction_choice(command)
                                else:
                                    if not self.opponent_direction:
                                        print(f"⏳ 請等待 {self.opponent_name} 先選擇方向...")
                                    else:
                                        print("❌ 現在不是你選擇方向的時候")
                            else:
                                print("❌ 你已經選擇過方向了")
                        elif command in ['1', '2', '3']:
                            print("❌ 現在是方向選擇階段，請選擇 4-7")
                    
                else:
                    print("❌ 未知指令。可用指令:")
                    if self.game_phase == 'rock_paper_scissors':
                        print("  • 1 - 剪刀 ✂️")
                        print("  • 2 - 石頭 🪨")
                        print("  • 3 - 布 📄")
                    elif self.game_phase == 'direction':
                        print("  • 4 - 上 ⬆️")
                        print("  • 5 - 下 ⬇️")
                        print("  • 6 - 左 ⬅️")
                        print("  • 7 - 右 ➡️")
                    print("  • quit - 離開遊戲")
                    
        except KeyboardInterrupt:
            # 用户按了 Ctrl+C，处理退出
            print(f"\n⚠️ 收到中斷信號...")
            if self.in_game:
                self.handle_quit_in_game()
            else:
                self.connected = False
        except Exception as e:
            pass

    def display_connection_status(self):
        """Display the current connection status"""
        print(f"\n{'='*50}")
        print(f"🔗 連線狀態")
        print(f"📍 你是: {self.username}")
        if self.opponent_name:
            print(f"🤝 對手: {self.opponent_name}")
        print(f"{'='*50}")
    
    def send_game_message(self, game_data):
        """發送遊戲訊息"""
        try:
            if self.connection_socket and self.connected:
                message_str = json.dumps(game_data)
                self.connection_socket.send(message_str.encode('utf-8'))
                return True
        except Exception as e:
            print(f"Error sending game message: {e}")
        return False
    
    def show_choice_prompt(self):
        """顯示選擇提示"""
        print(f"\n🎮 輪到你了！請選擇：")
        print("1 - 剪刀 ✂️")
        print("2 - 石頭 🪨")
        print("3 - 布 📄")
        print(f"\n💡 {self.username} 輸入指令: 現在可以輸入選擇！")
    
    def determine_winner(self):
        """判斷勝負"""
        choice_name = {
            'scissors': '剪刀 ✂️',
            'rock': '石頭 🪨', 
            'paper': '布 📄'
        }
        
        print(f"\n🎯 結果揭曉：")
        print(f"  你: {choice_name[self.my_choice]}")
        print(f"  {self.opponent_name}: {choice_name[self.opponent_choice]}")
        
        if self.my_choice == self.opponent_choice:
            print("🤝 平手！")
        elif (
            (self.my_choice == 'rock' and self.opponent_choice == 'scissors') or
            (self.my_choice == 'scissors' and self.opponent_choice == 'paper') or
            (self.my_choice == 'paper' and self.opponent_choice == 'rock')
        ):
            print("🎉 你贏了！")
            self.my_score += 1
        else:
            print("😔 你輸了！")
            self.opponent_score += 1
        
        print(f"\n📊 目前比分: {self.username} {self.my_score} - {self.opponent_score} {self.opponent_name}")
        
        # 重設狀態等待下一輪
        self.reset_round_state()
        print("\n按 Enter 繼續下一輪，或輸入 'quit' 離開遊戲")
        print(f"💡 {self.username} 輸入指令: 現在可以輸入 Enter 或 quit")
    
    def reset_round_state(self):
        """重設回合狀態"""
        self.my_choice = None
        self.opponent_choice = None
        self.my_turn = False
        self.waiting_for_opponent = True
        
        # 重設兩階段遊戲狀態
        self.game_phase = 'rock_paper_scissors'
        self.rps_winner = None
        self.rps_loser = None
        self.my_direction = None
        self.opponent_direction = None
        self.direction_turn_order = []
        self.game_completed = True  # 標記遊戲完成
        
        print(f"等待 {self.opponent_name} 開始下一輪...")
        print(f"⚠️ 等待中，請不要輸入任何內容，只需按 Enter 等待！")
    
    def handle_rps_result(self, message):
        """處理猜拳結果"""
        choice_name = {
            'scissors': '剪刀 ✂️',
            'rock': '石頭 🪨', 
            'paper': '布 📄'
        }
        
        self.rps_winner = message.get('rps_winner')
        self.rps_loser = message.get('rps_loser')
        self.game_phase = message.get('game_phase', 'direction')
        
        print(f"\n🎯 第一階段結果：")
        
        if self.rps_winner == 'player_a':
            print(f"😔 你猜拳輸了！")
        elif self.rps_winner == 'player_b':
            print(f"🎉 你猜拳贏了！")
        else:
            print("🔄 猜拳平手，重新開始！")
            # 重置猜拳狀態，準備重新猜拳
            self.my_choice = None
            self.opponent_choice = None
            self.my_turn = False
            self.waiting_for_opponent = True
            self.game_completed = False
            print(f"等待 {self.opponent_name} 重新開始猜拳...")
        
        if self.game_phase == 'direction':
            print("\n" + "="*50)
            print("🎯 進入第二階段：猜方向！")
            print("規則：猜拳輸的人先選方向，猜拳贏的人後選")
            print("如果猜拳贏的人選的方向和輸的人一樣 → 猜拳贏的人獲得最終勝利")
            print("如果方向不一樣 → 平手")
            print("="*50)
            
            # 根據消息中的信息決定誰先選
            direction_first = message.get('direction_first')
            if direction_first == 'player_b':
                # 我先選方向
                self.direction_turn_order = ['player_b', 'player_a']
                print(f"\n🎯 你猜拳輸了，請先選擇方向：")
                self.show_direction_choices()
            else:
                # 對手先選，我等待
                self.direction_turn_order = ['player_a', 'player_b']
                print(f"\n⏳ 你猜拳贏了！等待 {self.opponent_name} 先選擇方向...")
    

        
    def show_direction_choices(self):
        """顯示方向選擇"""
        print("方向選擇：")
        print("4 - 上 ⬆️")
        print("5 - 下 ⬇️")  
        print("6 - 左 ⬅️")
        print("7 - 右 ➡️")
        print(f"\n💡 {self.username} 輸入指令: 現在可以輸入方向選擇！")
    
    def handle_direction_choice(self, choice):
        """處理方向選擇"""
        direction_map = {
            '4': 'up',
            '5': 'down', 
            '6': 'left',
            '7': 'right'
        }
        
        if choice not in direction_map:
            return False
            
        direction = direction_map[choice]
        direction_emoji = {'up': '⬆️', 'down': '⬇️', 'left': '⬅️', 'right': '➡️'}
        
        self.my_direction = direction
        print(f"你選擇了：{direction_emoji[direction]}")
        
        # 發送我的方向選擇
        self.send_game_message({
            'type': 'direction_choice',
            'direction': direction,
            'player': 'player_b'
        })
        
        if self.rps_loser == 'player_b':
            # 我先選完了，通知對手選擇
            print(f"⏳ 等待 {self.opponent_name} 選擇方向...")
        
        return True
    
    def handle_opponent_direction_choice(self, message):
        """處理對手的方向選擇"""
        self.opponent_direction = message.get('direction')
        print(f"{self.opponent_name} 已完成方向選擇")
        
        # 如果我還沒選，檢查是否輪到我
        if not self.my_direction:
            if (self.rps_loser == 'player_a' and self.rps_winner == 'player_b'):
                # 對手輸了先選，現在輪到我
                print(f"🎯 現在輪到你選擇方向：")
                self.show_direction_choices()
            elif self.direction_turn_order and len(self.direction_turn_order) > 1 and self.direction_turn_order[1] == 'player_b':
                # 按照輪次順序，第二個是我
                print(f"🎯 現在輪到你選擇方向：")
                self.show_direction_choices()
    
    def handle_final_game_result(self, message):
        """處理最終遊戲結果"""
        direction_emoji = {'up': '⬆️', 'down': '⬇️', 'left': '⬅️', 'right': '➡️'}
        
        player_a_direction = message.get('player_a_direction')
        player_b_direction = message.get('player_b_direction')
        final_winner = message.get('final_winner')
        player_a_score = message.get('player_a_score')
        player_b_score = message.get('player_b_score')
        rps_winner = message.get('rps_winner')
        
        # 更新我的分數
        self.my_score = player_b_score
        self.opponent_score = player_a_score
        
        print(f"\n🏆 最終結果：")
        print(f"  你的方向: {direction_emoji[player_b_direction]}")
        print(f"  {self.opponent_name}的方向: {direction_emoji[player_a_direction]}")
        
        # 檢查是否遊戲結束
        game_over = message.get('game_over', False)
        
        if not game_over:
            # 只有在遊戲未結束時才給予單輪獎勵
            if final_winner == 'player_b':
                print("🎉🎉 恭喜！你獲得最終勝利！")
                # 贏家獎勵
                winner_stats = {'in_game_currency': 10, 'experience_points': 50}
                self.update_lobby_stats(winner_stats)
                print("💰 你獲得了 10 枚遊戲幣！")
                print("⭐ 你獲得了 50 經驗值！")
            elif final_winner == 'player_a':
                print("😔 對手獲得最終勝利！")
                # 輸家獎勵  
                loser_stats = {'in_game_currency': -10, 'experience_points': 20}
                self.update_lobby_stats(loser_stats)
                print("💸 你失去了 10 枚遊戲幣")
                print("⭐ 你獲得了 20 參與經驗值！")
            else:  # tie
                print("🤝 最終平手！")
                # 平手獎勵
                tie_stats = {'in_game_currency': 0, 'experience_points': 30}
                self.update_lobby_stats(tie_stats)
                print("⭐ 你獲得了 30 經驗值！")
        
        print(f"\n📊 目前比分: {self.username} {self.my_score} - {self.opponent_score} {self.opponent_name}")
        
        if game_over:
            # 檢查誰達到3分並給予相應獎勵
            if self.my_score >= 3:
                print("\n🎊 恭喜！你達到了 3 分，贏得整場遊戲！")
                print("🏆 你獲得晉級獎勵！")
                # 獲勝者晉級獎勵：500 XP (足夠升一級）
                self.update_lobby_stats({'experience_points': 500})
                print("⭐ 獲得 500 經驗值 (晉級獎勵)！")
            elif self.opponent_score >= 3:
                print("\n😔 對手達到了 3 分，贏得整場遊戲！")
                self.update_lobby_stats({'experience_points': -100})
                print("⭐ 失去 100 經驗值！")
            
            print("\n🏁 遊戲結束！感謝參與！")
            print("程序將在 3 秒後自動退出...")
            import time
            time.sleep(3)
            self.connected = False
            return
        
        # 重設遊戲狀態
        self.reset_round_state()
    

    
    def end_connection_session(self, apply_penalty=True):
        """Clean up after connection session ends"""
        self.connected = False
        
        # 如果在遊戲期間斷線，發送quit消息讓對手獲得獎勵
        if self.in_game and not self.game_completed and apply_penalty:
            if self.connection_socket:
                try:
                    quit_msg = {
                        'type': 'opponent_quit',
                        'message': f'{self.username} 已離開遊戲',
                        'reward_winner': True
                    }
                    self.connection_socket.send(json.dumps(quit_msg).encode('utf-8'))
                except:
                    pass
            # 自己也要被扣分
            print("💸 遊戲中途離開，已扣除 100 XP 作為懲罰")
            self.update_user_stats(-100, 0)
        
        self.in_game = False
        
        # Reset invitation state
        self.has_pending_invitation = False
        self.pending_invitation = None
        
        if self.connection_socket:
            try:
                self.connection_socket.close()
            except:
                pass
            self.connection_socket = None
        
        self.opponent_name = None
        
        print("\n🏁 Connection session ended.")
        print("Returning to invitation listener...")
        
        # Restart UDP listener
        self.start_listening()
        
        # Restart 60-second timeout timer
        self.start_timeout_timer()
        print("⏰ 重新啟動60秒超時計時器")
    
    def start_lobby_monitor(self):
        """啟動 lobby 連接監控線程"""
        if not self.lobby_monitor_thread:
            self.lobby_monitor_thread = threading.Thread(target=self.monitor_lobby_connection, daemon=True)
            self.lobby_monitor_thread.start()
    
    def monitor_lobby_connection(self):
        """監控 lobby 伺服器連接狀態"""
        try:
            while self.logged_in and self.lobby_socket:
                try:
                    # 每 5 秒發送一個心跳檢查
                    time.sleep(5)
                    
                    if not self.lobby_socket or not self.logged_in:
                        break
                    
                    # 發送心跳包
                    heartbeat = {'action': 'heartbeat'}
                    self.lobby_socket.settimeout(3.0)  # 3秒超時
                    self.lobby_socket.send(json.dumps(heartbeat).encode('utf-8'))
                    
                    # 嘗試接收回應
                    response_data = self.lobby_socket.recv(1024).decode('utf-8')
                    if not response_data:
                        raise ConnectionError("Lobby server disconnected")
                    
                    response = json.loads(response_data)
                    if response.get('status') != 'success':
                        raise ConnectionError("Heartbeat failed")
                        
                except (socket.timeout, ConnectionError, json.JSONDecodeError, Exception) as e:
                    print(f"\n❌ Lobby 伺服器連接中斷！程序將自動退出...")
                    print(f"原因: {e}")
                    self.handle_lobby_disconnect()
                    break
                    
        except Exception as e:
            print(f"Lobby 監控線程錯誤: {e}")
            self.handle_lobby_disconnect()
    
    def handle_lobby_disconnect(self):
        """處理 lobby 斷線"""
        self.logged_in = False
        self.listening = False
        
        # 結束遊戲連接
        if self.connected:
            self.end_connection_session()
        
        # 清理資源
        if self.lobby_socket:
            try:
                self.lobby_socket.close()
            except:
                pass
            self.lobby_socket = None
        
        # 強制退出程序
        print("🚪 因為 Lobby 伺服器斷線，程序即將退出...")
        import sys
        import os
        os._exit(1)  # 強制退出，不執行 cleanup
    
    def update_lobby_stats(self, stats):
        """Update user statistics on lobby server"""
        if self.lobby_socket and self.logged_in:
            try:
                update_request = {
                    'action': 'update_stats',
                    'stats': stats
                }
                
                self.lobby_socket.settimeout(5.0)  # 5秒超時
                self.lobby_socket.send(json.dumps(update_request).encode('utf-8'))
                response_data = self.lobby_socket.recv(1024).decode('utf-8')
                response = json.loads(response_data)
                
                if response['status'] == 'success':
                    print("✓ Stats updated on lobby server")
                    if 'user_data' in response:
                        user_data = response['user_data']
                        print(f"  Level: {user_data['level']}, XP: {user_data['experience_points']}, 遊戲幣: {user_data['in_game_currency']}")
                else:
                    print(f"Stats update failed: {response['message']}")
            
            except (socket.timeout, ConnectionError, json.JSONDecodeError) as e:
                print(f"❌ Lobby 連接問題，無法更新統計: {e}")
                self.handle_lobby_disconnect()
            except Exception as e:
                print(f"Error updating stats: {e}")
    
    def show_level_info(self):
        """显示等級和升級進度資訊"""
        if not (self.lobby_socket and self.logged_in):
            print("❌ 未連接到大廳伺服器")
            return
            
        try:
            # 獲取當前用戶資訊
            info_request = {'action': 'get_user_info'}
            self.lobby_socket.send(json.dumps(info_request).encode('utf-8'))
            response_data = self.lobby_socket.recv(1024).decode('utf-8')
            response = json.loads(response_data)
            
            if response['status'] == 'success':
                user_data = response['user_data']
                current_level = user_data['level']
                current_xp = user_data['experience_points']
                
                # 計算當前等級的 XP 範圍 (每 500 XP 一級)
                level_start_xp = (current_level - 1) * 500
                level_end_xp = current_level * 500
                level_progress_xp = current_xp - level_start_xp
                next_level_need_xp = level_end_xp - current_xp
                
                print(f"🎆 等級資訊")
                print(f"目前等級: {current_level}")
                print(f"總經驗值: {current_xp} XP")
                print(f"💰 遊戲幣: {user_data['in_game_currency']} 幣")
                print(f"本等級進度: {level_progress_xp}/500 XP")
                if next_level_need_xp > 0:
                    progress_percentage = (level_progress_xp * 100) // 500
                    progress_bar = "█" * (progress_percentage // 10) + "░" * (10 - progress_percentage // 10)
                    print(f"進度條: [{progress_bar}] {progress_percentage}%")
                    print(f"升下一級還需: {next_level_need_xp} XP")
                else:
                    print(f"恭喜！你已經満級了！")
                    
                print(f"🎮 獎勵方式 (每 500 XP 一級):")
                print(f"• 登入: +50 XP")
                print(f"• 遊戲勝利: +50 XP")
                print(f"• 遊戲失敗: +20 XP")
                print(f"• 遊戲平手: +30 XP")
                
            else:
                print(f"❌ 獲取等級資訊失敗: {response['message']}")
                
        except (socket.timeout, ConnectionError, json.JSONDecodeError) as e:
            print(f"❤️ Lobby 連接問題，無法獲取等級資訊: {e}")
            self.handle_lobby_disconnect()
        except Exception as e:
            print(f"獲取等級資訊時發生錯誤: {e}")
    
    def exchange_xp_for_currency(self):
        """兌換經驗值為遊戲幣"""
        if not (self.lobby_socket and self.logged_in):
            print("❌ 未連接到大廳伺服器")
            return
            
        try:
            # 先獲取當前用戶資訊
            info_request = {'action': 'get_user_info'}
            self.lobby_socket.settimeout(5.0)  # 5秒超時
            self.lobby_socket.send(json.dumps(info_request).encode('utf-8'))
            response_data = self.lobby_socket.recv(1024).decode('utf-8')
            response = json.loads(response_data)
            
            if response['status'] == 'success':
                user_data = response['user_data']
                current_xp = user_data['experience_points']
                current_currency = user_data['in_game_currency']
                
                max_exchange = current_xp // 10
                if max_exchange <= 0:
                    print(f"❌ 經驗值不足！目前 XP: {current_xp}，需要至少 10 XP 才能兌換")
                    return
                
                print(f"💰 經驗值兌換遊戲幣")
                print(f"目前 XP: {current_xp}，遊戲幣: {current_currency}")
                print(f"最多可兌換: {max_exchange} 枚遊戲幣 (消耗 {max_exchange * 10} XP)")
                
                try:
                    exchange_amount = int(input("請輸入要兌換的遊戲幣數量: ").strip())
                    
                    if exchange_amount <= 0:
                        print("❌ 兌換數量必須大於 0")
                        return
                    elif exchange_amount > max_exchange:
                        print(f"❌ 兌換數量超過限制！最多可兌換 {max_exchange} 枚")
                        return
                    
                    # 執行兌換
                    exchange_stats = {
                        'experience_points': -exchange_amount * 10,
                        'in_game_currency': exchange_amount
                    }
                    
                    self.update_lobby_stats(exchange_stats)
                    print(f"✓ 成功兌換 {exchange_amount} 枚遊戲幣！消耗了 {exchange_amount * 10} XP")
                    
                except ValueError:
                    print("❌ 請輸入有效的數字")
                except (KeyboardInterrupt, EOFError):
                    print("\n取消兌換")
            else:
                print(f"❌ 獲取用戶資訊失敗: {response['message']}")
                
        except (socket.timeout, ConnectionError, json.JSONDecodeError) as e:
            print(f"❌ Lobby 連接問題，無法進行兌換: {e}")
            self.handle_lobby_disconnect()
        except Exception as e:
            print(f"兌換過程發生錯誤: {e}")
    
    def start_listening(self):
        """Start the UDP listener thread"""
        if not self.connected:
            self.udp_thread = threading.Thread(target=self.start_udp_listener, daemon=True)
            self.udp_thread.start()
    
    def start_timeout_timer(self):
        """Start 60-second timeout timer"""
        self.start_time = time.time()
        print(f"⏰ 啟動60秒超時計時器 ({time.strftime('%H:%M:%S')})")
        self.timeout_thread = threading.Thread(target=self.timeout_monitor, daemon=True)
        self.timeout_thread.start()
    
    def timeout_monitor(self):
        """Monitor timeout and disconnect if no invitation received"""
        try:
            print(f"🕐 超時監控已啟動，60秒倒計時開始...")
            
            while not self.connected and not self.has_pending_invitation and self.logged_in:
                elapsed_time = time.time() - self.start_time
                remaining_time = self.timeout_seconds - elapsed_time
                
                # 每10秒顯示一次倒計時
                if int(remaining_time) % 10 == 0 and remaining_time > 0:
                    print(f"⏳ 還有 {int(remaining_time)} 秒自動斷線...")
                
                if remaining_time <= 0:
                    print(f"\n⏰ 60秒內無人邀請，自動斷線...")
                    print("🚪 程序即將退出...")
                    self.cleanup()
                    os._exit(0)
                    return
                
                # 每秒檢查一次
                time.sleep(1)
                
            print("✅ 超時監控結束 (收到邀請或建立連接)")
        except KeyboardInterrupt:
            print(f"\n⚠️ 超時監控收到中斷信號，提前結束")
            self.cleanup()
            os._exit(0)
        except Exception as e:
            print(f"Timeout monitor error: {e}")
    
    def reset_timeout_timer(self):
        """Reset timeout timer when invitation is received"""
        self.start_time = time.time()
    
    def stop_timeout_timer(self):
        """Stop timeout timer"""
        # 超時線程會自然結束，因為條件不再滿足
        pass
    
    def run(self):
        """Main run loop for Player B"""
        print(f"Starting Player B ({self.username})...")
        
        # 如果已經登入，跳過連線流程
        if self.logged_in and self.lobby_socket:
            print("✅ 使用現有登入狀態")
        else:
            # Connect to lobby server with retry
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                if self.connect_to_lobby():
                    break
                
                retry_count += 1
                print(f"❌ 連接失敗 (嘗試 {retry_count}/{max_retries})")
            
            if retry_count < max_retries:
                print("\n請選擇操作:")
                print("1. 重新嘗試登入")
                print("2. 註冊新的帳號")
                print("3. 退出程序")
                
                while True:
                    choice = input("\n請輸入選項 (1-3): ").strip()
                    if choice == "1":
                        # 重新輸入帳號密碼，並切換為登入模式
                        print(f"\n🔐 重新輸入登入資訊")
                        self.username = input("Username: ")
                        self.password = input("Password: ")
                        self.register_mode = False  # 切換為登入模式
                        break
                    elif choice == "2":
                        # 註冊新的帳號
                        print(f"\n📝 註冊新的帳號")
                        self.username = input("新的 Username: ")
                        while True:
                            self.password = input("新的 Password: ")
                            confirm_password = input("確認 Password: ")
                            if self.password == confirm_password:
                                break
                            else:
                                print("❌ 密碼不一致，請重新輸入")
                        self.register_mode = True  # 切換為註冊模式
                        break
                    elif choice == "3":
                        print("👋 退出程序")
                        return
                    else:
                        print("❌ 無效選項，請重新輸入")
            
            if retry_count >= max_retries:
                print("❌ 多次嘗試失敗，程序退出")
                return
        
        # 自動尋找可用的UDP端口
        print(f"🔍 正在尋找可用的UDP端口...")
        available_port = self.find_available_udp_port()
        if available_port:
            self.udp_port = available_port
            print(f"✓ 預分配端口: {self.udp_port}")
        else:
            print(f"⚠️ 無法找到可用端口，將在監聽時動態分配")
            # 不設置預設值，讓系統自動分配
            self.udp_port = 0
        
        # Start 30-second timeout timer first
        self.start_timeout_timer()
        
        # Start listening for invitations (with error handling)
        try:
            self.start_listening()
        except Exception as e:
            print(f"❌ 無法啟動UDP監聽器: {e}")
            print("⏰ 超時計時器仍然運行，60秒後自動退出...")
            # 不要 return，讓超時計時器繼續工作
        
        print(f"\n🎮 玩家 {self.username} 已就緒！")
        print(f"📡 正在監聽遊戲邀請 (UDP 端口 {self.udp_port})")
        print("⏳ 等待其他玩家邀請...")
        print(f"⏰ 60秒內無邀請將自動斷線")
        print("\n可用指令:")
        print("  'exchange' - 兌換經驗值為遊戲幣 (10XP = 1幣)")
        print("  'level' - 查看等級和升級進度")
        print("  'quit' - 退出程序")
        print("💡 或按 Ctrl+C 退出程序")
        
        try:
            while True:
                if self.connected:
                    # Connection is handled in connection_session, just wait
                    time.sleep(0.1)
                elif self.has_pending_invitation:
                    # Handle pending invitation
                    try:
                        response = input().strip().lower()
                        if response in ['y', 'yes']:
                            self.accept_invitation(
                                self.pending_invitation['inviter'], 
                                self.pending_invitation['address']
                            )
                        else:
                            self.decline_invitation(
                                self.pending_invitation['inviter'], 
                                self.pending_invitation['address']
                            )
                        
                        # Clear pending invitation
                        self.has_pending_invitation = False
                        self.pending_invitation = None
                        
                    except KeyboardInterrupt:
                        print(f"\n⚠️ 收到中斷信號，拒絕邀請並退出...")
                        self.decline_invitation(
                            self.pending_invitation['inviter'], 
                            self.pending_invitation['address']
                        )
                        self.has_pending_invitation = False
                        self.pending_invitation = None
                        raise  # 重新拋出以退出程序
                else:
                    # Handle commands while waiting for invitations
                    try:
                        import select
                        import sys
                        
                        # Check for input without blocking
                        if sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
                            command_input = input().strip().lower()
                            
                            if command_input == 'quit':
                                print("🚪 退出遊戲...")
                                break
                            elif command_input == 'exchange':
                                self.exchange_xp_for_currency()
                            elif command_input == 'level':
                                self.show_level_info()
                            elif command_input:
                                print("❌ 未知指令。可用指令: exchange, level, quit")
                        else:
                            time.sleep(0.1)
                    except KeyboardInterrupt:
                        raise  # 重新拋出KeyboardInterrupt，讓外層處理
                    except Exception:
                        time.sleep(1)
        
        except KeyboardInterrupt:
            print(f"\n正在關閉 {self.username} 的遊戲...")
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        self.listening = False
        self.connected = False
        
        # 停止 lobby 監控
        self.logged_in = False
        
        if self.udp_socket:
            self.udp_socket.close()
        
        if self.connection_socket:
            self.connection_socket.close()
        
        if self.lobby_socket:
            try:
                # Send logout message
                logout_request = {'action': 'logout'}
                self.lobby_socket.send(json.dumps(logout_request).encode('utf-8'))
                self.lobby_socket.close()
            except:
                pass
        
        print(f"玩家 {self.username} 已離線。")


def login_and_select_role():
    """登入並選擇角色的主函數"""
    print("🎮 歡迎來到黑白切遊戲！")
    print("=" * 50)
    
    # 詢問是註冊還是登入
    while True:
        mode = input("選擇模式 (1: 登入, 2: 註冊): ").strip()
        if mode in ['1', '2']:
            register_mode = (mode == '2')
            break
        print("❌ 無效選擇，請輸入 1 或 2")
    
    # 輸入帳號密碼
    username = input("輸入用戶名: ").strip()
    
    if register_mode:
        # 註冊模式需要確認密碼
        print("📝 註冊新帳號")
        while True:
            password = input("輸入密碼 (至少4位字符): ").strip()
            if not password:
                print("❌ 密碼不能為空！")
                continue
            if len(password) < 4:
                print("❌ 密碼長度至少需要4位字符！")
                continue
            
            confirm_password = input("確認密碼: ").strip()
            if password == confirm_password:
                print("✅ 密碼確認成功")
                break
            else:
                print("❌ 密碼不一致，請重新輸入")
    else:
        # 登入模式直接輸入密碼
        password = input("輸入密碼: ").strip()
    
    if not username or not password:
        print("❌ 用戶名和密碼不能為空！")
        return
    
    # 創建臨時玩家實例來進行登入測試
    try:
        # 使用 PlayerA 來測試登入（任一個類都可以用來測試登入）
        temp_player = PlayerA(username, password, register_mode=register_mode)
        login_success = temp_player.connect_to_lobby()
        
        if not login_success:
            print("❌ 登入失敗，請檢查帳號密碼")
            temp_player.cleanup()
            return
            
        # 登入成功，顯示角色選擇選單
        print("\n✅ 登入成功！")
        print("=" * 30)
        print("請選擇你的角色:")
        print("1️⃣  Player A - 遊戲發起者")
        print("   • 可以掃描並邀請其他玩家")
        print("   • 主動發起遊戲對戰")
        print("   • 需要找到 Player B 來對戰")
        print()
        print("2️⃣  Player B - 遊戲接受者") 
        print("   • 等待其他玩家的邀請")
        print("   • 被動接受遊戲對戰")
        print("   • 監聽並回應邀請")
        print("=" * 30)
        
        # 獲取並保存 lobby 連線信息
        lobby_host = temp_player.lobby_host
        lobby_socket = temp_player.lobby_socket
        temp_player.lobby_socket = None  # 防止被清理掉
        
        # 清理臨時玩家的其他資源（但保留 lobby_socket）
        temp_player.logged_in = False
        if temp_player.udp_socket:
            temp_player.udp_socket.close()
        if temp_player.tcp_socket:
            temp_player.tcp_socket.close()
        
        while True:
            choice = input("選擇角色 (1: Player A, 2: Player B): ").strip()
            
            if choice == '1':
                print("\n🎯 你選擇了 Player A (遊戲發起者)")
                print("正在初始化...")
                player = PlayerA(username, password, lobby_host=lobby_host)
                # 重用已存在的連線
                player.lobby_socket = lobby_socket
                player.logged_in = True
                player.start_lobby_monitor()
                player.run()
                break
                
            elif choice == '2':
                print("\n🎧 你選擇了 Player B (遊戲接受者)")
                print("正在初始化...")
                player = PlayerB(username, password, lobby_host=lobby_host)
                # 重用已存在的連線
                player.lobby_socket = lobby_socket
                player.logged_in = True
                player.start_lobby_monitor()
                player.run()
                break
                
            else:
                print("❌ 無效選擇，請輸入 1 或 2")
                
    except KeyboardInterrupt:
        print("\n👋 程序已退出")
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")


if __name__ == "__main__":
    login_and_select_role()