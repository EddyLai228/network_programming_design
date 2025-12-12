import socket
import threading
import json
import time
import sys
import os

# Add src directory to path for imports
sys.path.append(os.path.dirname(__file__))

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
                # Test if port is available
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                test_socket.bind(('127.0.0.1', test_port))  # 綁定所有網卡
                test_socket.close()
                print(f"🔍 找到可用UDP端口: {test_port}")
                return test_port
            except OSError:
                continue
        return None
    
    def start_udp_listener(self):
        """Start listening for UDP invitations"""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to the already selected available port
            try:
                self.udp_socket.bind(('0.0.0.0', self.udp_port))  # 綁定所有網卡
                print(f"✓ UDP監聽器綁定到 0.0.0.0:{self.udp_port}")
            except OSError as e:
                # Port might have been taken since we checked, try to find another one
                print(f"⚠️ 端口 {self.udp_port} 已被佔用，重新尋找...")
                new_port = self.find_available_udp_port()
                if new_port:
                    self.udp_port = new_port
                    self.udp_socket.bind(('0.0.0.0', self.udp_port))
                    print(f"✓ 改用端口: {self.udp_port}")
                else:
                    raise Exception("無法找到可用的UDP端口")
            
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
                        
                        # Stop UDP listener
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
        
        try:
            # Main connection loop
            while self.connected:
                # Check for incoming messages first
                self.connection_socket.settimeout(0.1)
                try:
                    data = self.connection_socket.recv(1024).decode('utf-8')
                    if not data:
                        print("🔌 對手已斷線")
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
        
        except Exception as e:
            print(f"Connection session error: {e}")
        
        finally:
            self.end_connection_session()
    
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
            print("🚪 遊戲結束，正在退出...")
            self.connected = False
            return
        
        elif msg_type == 'disconnect':
            print("⚠️ 對手已斷線，遊戲結束")
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
    

    
    def end_connection_session(self):
        """Clean up after connection session ends"""
        self.connected = False
        self.in_game = False
        
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
    
    def start_listening(self):
        """Start the UDP listener thread"""
        if not self.connected:
            self.udp_thread = threading.Thread(target=self.start_udp_listener, daemon=True)
            self.udp_thread.start()
    
    def run(self):
        """Main run loop for Player B"""
        print(f"Starting Player B ({self.username})...")
        
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
            print(f"✓ 找到可用端口: {self.udp_port}")
        else:
            print(f"⚠️ 無法找到可用端口，使用預設值: {self.udp_port}")
        
        # Start listening for invitations
        self.start_listening()
        
        print(f"\n🎮 玩家 {self.username} 已就緒！")
        print(f"📡 正在監聽遊戲邀請 (UDP 端口 {self.udp_port})")
        print("⏳ 等待其他玩家邀請...")
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
                        self.decline_invitation(
                            self.pending_invitation['inviter'], 
                            self.pending_invitation['address']
                        )
                        self.has_pending_invitation = False
                        self.pending_invitation = None
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
                    except:
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

def main():
    """Main function"""
    if len(sys.argv) >= 3:
        username = sys.argv[1]
        password = sys.argv[2]
        udp_port = int(sys.argv[3]) if len(sys.argv) > 3 else 10000
        # 命令列模式，預設為登入
        action = "login"
    else:
        # 互動模式，讓用戶選擇註冊或登入
        print("🎮 歡迎使用黑白切線上遊戲系統")
        print("=" * 45)
        
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
        
        # UDP 端口會自動尋找可用端口
        udp_port = 10000  # 起始端口
    
    player = PlayerB(username, password, udp_port=udp_port, register_mode=(action == "register" if 'action' in locals() else False))
    player.run()

if __name__ == "__main__":
    main()