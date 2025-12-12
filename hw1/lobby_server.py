import socket
import threading
import json
import hashlib
import time
import os
from datetime import datetime

def detect_server_ip():
    """自動檢測當前伺服器的 IP 位址"""
    try:
        # 方法1: 檢查是否在 NYCU 伺服器上
        hostname = socket.gethostname()
        print(f"🔍 檢測到主機名: {hostname}")
        
        if 'linux1.cs.nycu.edu.tw' in hostname:
            return '140.113.235.151'
        elif 'linux2.cs.nycu.edu.tw' in hostname:
            return '140.113.235.152'
        elif 'linux3.cs.nycu.edu.tw' in hostname:
            return '140.113.235.153'
        elif 'linux4.cs.nycu.edu.tw' in hostname:
            return '140.113.235.154'

        # 方法3: 預設使用 127.0.0.1 
        print("⚠️ 無法檢測具體 IP，使用 127.0.0.1 綁定所有介面")
        return '127.0.0.1'

    except Exception as e:
        print(f"❌ IP 檢測失敗: {e}")
        return '127.0.0.1'

class LobbyServer:
    def __init__(self, host=None, port=12000):
        # 動態檢測 host IP
        if host is None:
            self.host = detect_server_ip()
            print(f"🖥️ Lobby server 將綁定到: {self.host}")
        else:
            self.host = host
        
        self.port = port
        self.socket = None
        self.running = False
        
        # Database file path - same directory as lobby_server.py
        self.db_file = os.path.join(os.path.dirname(__file__), 'users.json')
        
        # In-memory user database and active sessions
        self.users = {}
        self.active_sessions = {}  # username -> {socket, login_time, status}
        
        # Load existing users from file
        self.load_users()
        
        # Thread lock for database operations
        self.db_lock = threading.Lock()
    
    def load_users(self):
        """Load users from persistent storage"""
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'r') as f:
                    self.users = json.load(f)
                print(f"Loaded {len(self.users)} users from database")
            else:
                print("No existing database found, starting with empty user list")
        except Exception as e:
            print(f"Error loading users: {e}")
            self.users = {}
    
    def save_users(self):
        """Save users to persistent storage"""
        try:
            with open(self.db_file, 'w') as f:
                json.dump(self.users, f, indent=2)
        except Exception as e:
            print(f"Error saving users: {e}")
    
    def hash_password(self, password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def register_user(self, username, password):
        """Register a new user"""
        with self.db_lock:
            if username in self.users:
                return {
                    'status': 'error',
                    'message': 'Username already exists'
                }
            
            # Create new user entry
            self.users[username] = {
                'password': self.hash_password(password),
                'created_at': datetime.now().isoformat(),
                'login_count': 0,
                'experience_points': 0,
                'level': 1,
                'in_game_currency': 100
            }
            
            # Save to file
            self.save_users()
            
            return {
                'status': 'success',
                'message': 'Registration successful'
            }
    
    def login_user(self, username, password, client_socket):
        """Login user and create session"""
        with self.db_lock:
            if username not in self.users:
                return {
                    'status': 'error',
                    'message': 'User not found'
                }
            
            # Check password
            if self.users[username]['password'] != self.hash_password(password):
                return {
                    'status': 'error',
                    'message': 'Invalid password'
                }
            
            # Check for duplicate login
            if username in self.active_sessions:
                return {
                    'status': 'error',
                    'message': 'User already logged in'
                }
            
            # Update user stats
            self.users[username]['login_count'] += 1
            self.users[username]['last_login'] = datetime.now().isoformat()
            
            # 每次登入送 50 XP
            old_level = self.users[username]['level']
            self.users[username]['experience_points'] += 50
            
            # 重新計算等級 (每 500 XP 一級)
            new_level = max(1, self.users[username]['experience_points'] // 500 + 1)
            self.users[username]['level'] = new_level
            
            # 檢查是否升級
            if new_level > old_level:
                print(f"🎉 {username} 登入升級了！{old_level} → {new_level}")
            
            # Create active session
            self.active_sessions[username] = {
                'socket': client_socket,
                'login_time': time.time(),
                'status': 'online'
            }
            
            # Save to file
            self.save_users()
            
            return {
                'status': 'success',
                'message': 'Login successful',
                'user_data': {
                    'username': username,
                    'login_count': self.users[username]['login_count'],
                    'experience_points': self.users[username]['experience_points'],
                    'level': self.users[username]['level'],
                    'in_game_currency': self.users[username]['in_game_currency']
                }
            }
    
    def logout_user(self, username):
        """Logout user and remove session"""
        with self.db_lock:
            if username in self.active_sessions:
                del self.active_sessions[username]
                print(f"User {username} logged out")
                return True
            return False
    
    def recalculate_all_levels(self):
        """重新計算所有用戶的等級"""
        with self.db_lock:
            updated_users = []
            for username, user_data in self.users.items():
                old_level = user_data['level']
                new_level = max(1, user_data['experience_points'] // 500 + 1)
                if new_level != old_level:
                    user_data['level'] = new_level
                    updated_users.append((username, old_level, new_level))
            
            if updated_users:
                self.save_users()
                print(f"🔄 重新計算等級完成:")
                for username, old, new in updated_users:
                    print(f"  {username}: {old} → {new}")
                return len(updated_users)
            return 0
    
    def update_user_stats(self, username, stats):
        """Update user statistics during gameplay"""
        with self.db_lock:
            if username in self.users and username in self.active_sessions:
                user_data = self.users[username]
                
                # Update stats if provided
                if 'experience_points' in stats:
                    user_data['experience_points'] += stats['experience_points']
                if 'in_game_currency' in stats:
                    # 確保金幣不會低於 0
                    user_data['in_game_currency'] = max(0, user_data['in_game_currency'] + stats['in_game_currency'])
                
                # Update level based on experience points (每 500 XP 一級)
                old_level = user_data['level']
                new_level = max(1, user_data['experience_points'] // 500 + 1)
                user_data['level'] = new_level
                
                # Check if user leveled up
                if new_level > old_level:
                    print(f"🎉 {username} 升級了！{old_level} → {new_level}")
                    # 可以在這裡添加升級獎勵
                    # user_data['in_game_currency'] += (new_level - old_level) * 50  # 升級獎勵
                
                # Save to file
                self.save_users()
                
                return {
                    'status': 'success',
                    'message': 'Stats updated',
                    'user_data': {
                        'username': username,
                        'experience_points': user_data['experience_points'],
                        'level': user_data['level'],
                        'in_game_currency': user_data['in_game_currency']
                    }
                }
            
            return {
                'status': 'error',
                'message': 'User not found or not logged in'
            }
    
    def handle_client(self, client_socket, address):
        """Handle individual client connection"""
        print(f"New connection from {address}")
        current_user = None
        
        try:
            while True:
                # Receive message from client
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                
                try:
                    message = json.loads(data)
                    action = message.get('action')
                    
                    if action == 'register':
                        username = message.get('username')
                        password = message.get('password')
                        
                        if not username or not password:
                            response = {
                                'status': 'error',
                                'message': 'Username and password required'
                            }
                        else:
                            response = self.register_user(username, password)
                        
                    elif action == 'login':
                        username = message.get('username')
                        password = message.get('password')
                        
                        if not username or not password:
                            response = {
                                'status': 'error',
                                'message': 'Username and password required'
                            }
                        else:
                            response = self.login_user(username, password, client_socket)
                            if response['status'] == 'success':
                                current_user = username
                    
                    elif action == 'logout':
                        if current_user:
                            self.logout_user(current_user)
                            response = {
                                'status': 'success',
                                'message': 'Logout successful'
                            }
                            current_user = None
                        else:
                            response = {
                                'status': 'error',
                                'message': 'Not logged in'
                            }
                    
                    elif action == 'update_stats':
                        if current_user:
                            stats = message.get('stats', {})
                            response = self.update_user_stats(current_user, stats)
                        else:
                            response = {
                                'status': 'error',
                                'message': 'Not logged in'
                            }
                    
                    elif action == 'get_user_info':
                        if current_user and current_user in self.users:
                            user_data = self.users[current_user]
                            response = {
                                'status': 'success',
                                'user_data': {
                                    'username': current_user,
                                    'login_count': user_data['login_count'],
                                    'experience_points': user_data['experience_points'],
                                    'level': user_data['level'],
                                    'in_game_currency': user_data['in_game_currency']
                                }
                            }
                        else:
                            response = {
                                'status': 'error',
                                'message': 'Not logged in'
                            }
                    
                    elif action == 'exchange_xp':
                        if current_user and current_user in self.users:
                            xp_amount = message.get('xp_amount', 0)
                            user_data = self.users[current_user]
                            
                            # 檢查 XP 是否足夠且為 10 的倍數
                            if xp_amount >= 10 and xp_amount % 10 == 0 and user_data['experience_points'] >= xp_amount:
                                coins_to_add = xp_amount // 10
                                
                                # 扣除 XP 並增加金幣
                                self.users[current_user]['experience_points'] -= xp_amount
                                self.users[current_user]['in_game_currency'] += coins_to_add
                                
                                # 儲存資料
                                self.save_users()
                                
                                response = {
                                    'status': 'success',
                                    'message': f'Successfully exchanged {xp_amount} XP for {coins_to_add} coins',
                                    'coins_gained': coins_to_add,
                                    'xp_used': xp_amount,
                                    'new_xp': self.users[current_user]['experience_points'],
                                    'new_currency': self.users[current_user]['in_game_currency']
                                }
                            else:
                                response = {
                                    'status': 'error',
                                    'message': 'Insufficient XP or invalid amount (must be multiple of 10)'
                                }
                        else:
                            response = {
                                'status': 'error',
                                'message': 'Not logged in'
                            }
                    
                    elif action == 'heartbeat':
                        # 心跳檢查 - 簡單回應確認連接狀態
                        if current_user:
                            response = {
                                'status': 'success',
                                'message': 'heartbeat_ok'
                            }
                        else:
                            response = {
                                'status': 'error',
                                'message': 'Not logged in'
                            }
                    
                    else:
                        response = {
                            'status': 'error',
                            'message': 'Unknown action'
                        }
                    
                    # Send response
                    client_socket.send(json.dumps(response).encode('utf-8'))
                
                except json.JSONDecodeError:
                    response = {
                        'status': 'error',
                        'message': 'Invalid JSON format'
                    }
                    client_socket.send(json.dumps(response).encode('utf-8'))
        
        except Exception as e:
            print(f"Error handling client {address}: {e}")
        
        finally:
            # Clean up on disconnect
            if current_user:
                self.logout_user(current_user)
            client_socket.close()
            print(f"Connection closed: {address}")
    
    def start(self):
        """Start the lobby server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(10)
            
            self.running = True
            print(f"🚀 Lobby server started on {self.host}:{self.port}")
            
            # 根據 host 顯示不同的訊息
            if self.host == '0.0.0.0':
                print(f"📡 Server listening on ALL network interfaces")
                print(f"🔗 Accessible from any IP on this machine")
            else:
                print(f"📡 Server bound to specific IP: {self.host}")
                print(f"🔗 Clients should connect to {self.host}:{self.port}")
            
            print("Waiting for connections...")
            
            while self.running:
                try:
                    client_socket, address = self.socket.accept()
                    
                    # Handle each client in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address),
                        daemon=True
                    )
                    client_thread.start()
                
                except socket.error as e:
                    if self.running:
                        print(f"Socket error: {e}")
                    break
        
        except Exception as e:
            print(f"Error starting server: {e}")
        
        finally:
            self.stop()
    
    def stop(self):
        """Stop the lobby server"""
        self.running = False
        if self.socket:
            self.socket.close()
        print("Lobby server stopped")
    
    def print_stats(self):
        """Print server statistics"""
        print("\n=== Lobby Server Statistics ===")
        print(f"Total registered users: {len(self.users)}")
        print(f"Active sessions: {len(self.active_sessions)}")
        
        if self.active_sessions:
            print("\nActive users:")
            for username, session_data in self.active_sessions.items():
                print(f"  - {username} (status: {session_data['status']})")
        
        if self.users:
            print("\nRegistered users:")
            for username, user_data in self.users.items():
                print(f"  - {username}: Level {user_data['level']}, "
                      f"XP: {user_data['experience_points']}, "
                      f"Currency: {user_data['in_game_currency']}, "
                      f"Logins: {user_data['login_count']}")
        print("=" * 30)

def main():
    """Main function to run the lobby server"""
    server = LobbyServer()
    
    try:
        # Start server in a separate thread so we can handle commands
        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        
        # Command loop
        print("\nLobby Server Commands:")
        print("  'stats' - Show server statistics")
        print("  'users' - List all registered users")
        print("  'fix' - Fix all user levels based on XP")
        print("  'quit' - Stop the server")
        
        while True:
            try:
                command = input().strip().lower()
                
                if command == 'quit':
                    print("Shutting down server...")
                    break
                elif command == 'stats':
                    server.print_stats()
                elif command == 'users':
                    print(f"\nRegistered users ({len(server.users)}):")
                    for username in server.users:
                        user_data = server.users[username]
                        status = "Online" if username in server.active_sessions else "Offline"
                        print(f"  {username} - Level {user_data['level']} ({status})")
                elif command == 'fix':
                    # 修復所有用戶的等級
                    updated = server.recalculate_all_levels()
                    if updated > 0:
                        print(f"✓ 已修復 {updated} 個用戶的等級")
                    else:
                        print("✓ 所有用戶等級都是正確的")
                else:
                    print("Unknown command. Use 'stats', 'users', 'fix', or 'quit'")
            
            except KeyboardInterrupt:
                break
            except EOFError:
                break
    
    finally:
        server.stop()

if __name__ == "__main__":
    main()