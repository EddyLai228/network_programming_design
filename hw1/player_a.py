import socket
import threading
import json
import time
import sys
import os

# Add src directory to path for imports
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
            self.udp_socket.settimeout(2.0)  # 2 second timeout per request
            
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
                    self.tcp_socket.bind(('0.0.0.0', port))  # 綁定所有網卡
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
            # 獲取本機實際IP地址
            import socket as sock
            try:
                # 嘗試連接外部地址來獲取本機IP
                with sock.socket(sock.AF_INET, sock.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    local_ip = s.getsockname()[0]
                print(f"🔍 檢測到本機IP: {local_ip}")
            except:
                # 如果無法連接外部，嘗試其他方法
                try:
                    local_ip = sock.gethostbyname(sock.gethostname())
                    print(f"🔍 使用主機名獲取IP: {local_ip}")
                except:
                    local_ip = "127.0.0.1"
                    print(f"⚠️ 無法獲取IP，使用預設: {local_ip}")
            
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
                    # 空輸入 (Enter) - 只有在遊戲完全結束時才開始新一輪
                    if self.game_completed:
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
                        break
                    
                    # 處理可能連在一起的多個JSON消息
                    self.process_received_data(data)
                
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"Error receiving message: {e}")
                    break
        
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
            print(f"⚠️ {quit_message}")
            print("🚪 遊戲結束，正在退出...")
            self.end_connection()
            return
        
        elif msg_type == 'disconnect':
            print("⚠️ 對手已斷線，遊戲結束")
            self.end_connection()
            return
        
        else:
            print(f"收到未知訊息類型: {msg_type}")
    
    def handle_quit_in_game(self):
        """處理遊戲中途退出的邏輯"""
        # 檢查是否在遊戲進行中（已開始但未結束）
        if self.game_started and not self.game_completed and not self.waiting_for_opponent:
            print("⚠️ 遊戲進行中離開將被扣除 100 XP!")
            
            # 通知對手玩家退出
            self.send_game_message({
                'type': 'opponent_quit',
                'message': f'{self.username} 已離開遊戲，雙方將強制退出'
            })
            
            # 扣除經驗值
            self.update_user_stats(-100, 0)
            print("💸 已扣除 100 XP 作為懲罰")
            
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
    
    def start_game(self):
        """開始新一輪遊戲"""
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
                print(f"• 登入: +100 XP")
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
    
    def end_connection(self):
        """End the current connection session"""
        self.connected = False
        self.in_game = False
        
        if self.opponent_socket:
            try:
                # Send disconnect message
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

def main():
    """Main function"""
    if len(sys.argv) >= 3:
        username = sys.argv[1]
        password = sys.argv[2]
        # 命令列模式，預設為登入
        action = "login"
    else:
        # 互動模式，讓用戶選擇註冊或登入
        print("🎮 歡迎使用黑白切線上遊戲系統")
        print("=" * 40)
        
        while True:
            print("\n請選擇操作:")
            print("1. 登入現有帳號")
            print("2. 註冊新帳號") 
            print("3. 退出")
            
            choice = input("\n請輸入選項 (1-3): ").strip()
            
            if choice == "1":
                action = "login"
                break
            elif choice == "2":
                action = "register"
                break
            elif choice == "3":
                print("再見！👋")
                return
            else:
                print("❌ 無效選項，請重新輸入")
        
        # 帳號密碼輸入循環
        while True:
            print(f"\n📝 {'註冊新帳號' if action == 'register' else '登入現有帳號'}")
            username = input("Username: ")
            if action == "register":
                while True:
                    password = input("Password: ")
                    confirm_password = input("確認 Password: ")
                    if password == confirm_password:
                        break
                    else:
                        print("❌ 密碼不一致，請重新輸入")
            else:
                password = input("Password: ")
            break
    
    player = PlayerA(username, password, register_mode=(action == "register" if 'action' in locals() else False))
    player.run()

if __name__ == "__main__":
    main()