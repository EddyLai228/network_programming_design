"""
Tic-Tac-Toe CLI - Multiplayer Game
A CLI version of tic-tac-toe for two players over network
"""

import socket
import json
import sys
import os
import threading


class TicTacToeGame:
    def __init__(self):
        self.board = [['' for _ in range(3)] for _ in range(3)]
        self.current_player = 'X'
        self.game_over = False
        self.winner = None
    
    def make_move(self, row, col, player):
        """Make a move on the board"""
        if self.board[row][col] != '':
            return False, "此位置已被佔據"
        
        self.board[row][col] = player
        
        # Check win
        if self.check_winner(player):
            self.game_over = True
            self.winner = player
            return True, f"玩家 {player} 獲勝!"
        
        # Check draw
        if self.is_board_full():
            self.game_over = True
            return True, "平局!"
        
        # Switch player
        self.current_player = 'O' if self.current_player == 'X' else 'X'
        return True, "移動成功"
    
    def check_winner(self, player):
        """Check if player has won"""
        # Check rows
        for row in range(3):
            if all(self.board[row][col] == player for col in range(3)):
                return True
        
        # Check columns
        for col in range(3):
            if all(self.board[row][col] == player for row in range(3)):
                return True
        
        # Check diagonals
        if all(self.board[i][i] == player for i in range(3)):
            return True
        if all(self.board[i][2-i] == player for i in range(3)):
            return True
        
        return False
    
    def is_board_full(self):
        """Check if board is full"""
        return all(self.board[row][col] != '' for row in range(3) for col in range(3))
    
    def get_board_state(self):
        """Get current board state"""
        return {
            'board': self.board,
            'current_player': self.current_player,
            'game_over': self.game_over,
            'winner': self.winner
        }
    
    def display_board(self):
        """Display the board in CLI"""
        print("\n" + "=" * 30)
        print("     井字遊戲 - 當前棋盤")
        print("=" * 30)
        print("\n     0   1   2")
        for i, row in enumerate(self.board):
            print(f"  {i}  ", end="")
            for j, cell in enumerate(row):
                display = cell if cell else ' '
                print(f" {display} ", end="")
                if j < 2:
                    print("|", end="")
            print()
            if i < 2:
                print("     " + "-" * 11)
        print()


class TicTacToeServer:
    def __init__(self, port=5001):
        self.port = port
        self.game = TicTacToeGame()
        self.clients = []
        self.client_symbols = {}  # socket -> 'X' or 'O'
        self.running = False
    
    def start(self):
        """Start the game server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(2)
        self.running = True
        
        print(f"\n{'=' * 50}")
        print(f"井字遊戲伺服器已啟動")
        print(f"監聽端口: {self.port}")
        print(f"等待玩家連線... (需要 2 位玩家)")
        print(f"{'=' * 50}\n")
        
        try:
            while len(self.clients) < 2:
                client_socket, address = self.server_socket.accept()
                self.clients.append(client_socket)
                
                # Assign symbol
                symbol = 'X' if len(self.clients) == 1 else 'O'
                self.client_symbols[client_socket] = symbol
                
                print(f"玩家 {len(self.clients)} 已連線 ({symbol}) - {address}")
                
                # Send welcome message
                self.send_message(client_socket, {
                    'type': 'welcome',
                    'symbol': symbol,
                    'message': f'歡迎! 你是玩家 {symbol}'
                })
            
            print(f"\n✓ 所有玩家已就緒，遊戲開始!\n")
            
            # Start game
            self.broadcast({
                'type': 'game_start',
                'message': '遊戲開始! 玩家 X 先手'
            })
            
            # Send initial board state
            self.broadcast_board_state()
            
            # Handle game
            threading.Thread(target=self.handle_player, args=(self.clients[0],), daemon=True).start()
            threading.Thread(target=self.handle_player, args=(self.clients[1],), daemon=True).start()
            
            # Keep server running
            while self.running:
                if self.game.game_over:
                    self.end_game()
                    break
                threading.Event().wait(0.1)
        
        except KeyboardInterrupt:
            print("\n\n伺服器關閉中...")
        finally:
            self.cleanup()
    
    def handle_player(self, client_socket):
        """Handle individual player"""
        try:
            while self.running and not self.game.game_over:
                data = self.recv_message(client_socket)
                if not data:
                    break
                
                if data['type'] == 'move':
                    self.handle_move(client_socket, data['row'], data['col'])
        
        except Exception as e:
            print(f"玩家連線錯誤: {e}")
        finally:
            if client_socket in self.clients:
                symbol = self.client_symbols.get(client_socket, '?')
                print(f"玩家 {symbol} 已斷線")
                self.clients.remove(client_socket)
    
    def handle_move(self, client_socket, row, col):
        """Handle a player's move"""
        player_symbol = self.client_symbols[client_socket]
        
        # Check if it's player's turn
        if self.game.current_player != player_symbol:
            self.send_message(client_socket, {
                'type': 'error',
                'message': '還不是你的回合'
            })
            return
        
        # Make move
        success, message = self.game.make_move(row, col, player_symbol)
        
        if success:
            print(f"玩家 {player_symbol} 下在位置 ({row}, {col})")
            self.game.display_board()
            
            # Broadcast new board state
            self.broadcast_board_state()
            
            if self.game.game_over:
                self.end_game()
        else:
            self.send_message(client_socket, {
                'type': 'error',
                'message': message
            })
    
    def broadcast_board_state(self):
        """Broadcast current board state to all players"""
        state = self.game.get_board_state()
        self.broadcast({
            'type': 'board_update',
            'board': state['board'],
            'current_player': state['current_player'],
            'game_over': state['game_over'],
            'winner': state['winner']
        })
    
    def end_game(self):
        """End the game"""
        self.running = False
        
        if self.game.winner:
            result = f"玩家 {self.game.winner} 獲勝!"
            print(f"\n🎉 {result}")
        else:
            result = "平局!"
            print(f"\n{result}")
        
        self.broadcast({
            'type': 'game_end',
            'winner': self.game.winner,
            'message': result
        })
        
        # Write game result to file
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(script_dir, 'game_result.txt'), 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"✅ 遊戲結果已寫入: {result}")
        except Exception as e:
            print(f"⚠️  無法寫入遊戲結果: {e}")
        
        print("\n伺服器將在 3 秒後關閉...")
        import time
        time.sleep(3)
    
    def broadcast(self, message):
        """Broadcast message to all clients"""
        for client in self.clients[:]:
            try:
                self.send_message(client, message)
            except:
                if client in self.clients:
                    self.clients.remove(client)
    
    def send_message(self, client_socket, message):
        """Send JSON message to client"""
        try:
            data = json.dumps(message).encode('utf-8')
            client_socket.sendall(len(data).to_bytes(4, 'big'))
            client_socket.sendall(data)
        except Exception as e:
            raise e
    
    def recv_message(self, client_socket):
        """Receive JSON message from client"""
        try:
            length_bytes = client_socket.recv(4)
            if not length_bytes:
                return None
            length = int.from_bytes(length_bytes, 'big')
            data = b''
            while len(data) < length:
                chunk = client_socket.recv(length - len(data))
                if not chunk:
                    return None
                data += chunk
            return json.loads(data.decode('utf-8'))
        except:
            return None
    
    def cleanup(self):
        """Cleanup resources"""
        for client in self.clients:
            try:
                client.close()
            except:
                pass
        try:
            self.server_socket.close()
        except:
            pass


class TicTacToeClient:
    def __init__(self, host='localhost', port=5001):
        self.host = host
        self.port = port
        self.socket = None
        self.my_symbol = None
        self.board = [['' for _ in range(3)] for _ in range(3)]
        self.current_player = 'X'
        self.game_over = False
        self.running = True
    
    def connect(self):
        """Connect to game server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            return True
        except Exception as e:
            print(f"連線失敗: {e}")
            return False
    
    def run(self):
        """Run the game client"""
        print(f"\n{'=' * 50}")
        print(f"井字遊戲客戶端")
        print(f"連線至: {self.host}:{self.port}")
        print(f"{'=' * 50}\n")
        
        if not self.connect():
            return
        
        print("✓ 已連線至伺服器，等待遊戲開始...\n")
        
        # Start receiver thread
        receiver_thread = threading.Thread(target=self.receive_messages, daemon=True)
        receiver_thread.start()
        
        # Game loop
        try:
            while self.running:
                if self.game_over:
                    break
                
                # Wait for player's turn
                if self.current_player == self.my_symbol and not self.game_over:
                    self.make_move()
                else:
                    threading.Event().wait(0.1)
        
        except KeyboardInterrupt:
            print("\n\n遊戲中斷")
        finally:
            self.cleanup()
    
    def receive_messages(self):
        """Receive messages from server"""
        try:
            while self.running:
                message = self.recv_message()
                if not message:
                    print("\n⚠️  與伺服器斷線")
                    self.running = False
                    break
                
                self.handle_message(message)
        except Exception as e:
            if self.running:
                print(f"\n接收訊息錯誤: {e}")
                self.running = False
    
    def handle_message(self, message):
        """Handle message from server"""
        msg_type = message.get('type')
        
        if msg_type == 'welcome':
            self.my_symbol = message['symbol']
            print(f"✓ {message['message']}")
        
        elif msg_type == 'game_start':
            print(f"\n{'=' * 50}")
            print(f"{message['message']}")
            print(f"{'=' * 50}\n")
        
        elif msg_type == 'board_update':
            self.board = message['board']
            self.current_player = message['current_player']
            self.game_over = message['game_over']
            self.display_board()
            
            if not self.game_over:
                if self.current_player == self.my_symbol:
                    print(f"\n🎮 輪到你了! (你是 {self.my_symbol})")
                else:
                    other = 'O' if self.my_symbol == 'X' else 'X'
                    print(f"\n⏳ 等待對手 ({other}) 下棋...")
        
        elif msg_type == 'game_end':
            self.game_over = True
            print(f"\n{'=' * 50}")
            if message['winner']:
                if message['winner'] == self.my_symbol:
                    print(f"🎉 恭喜! 你獲勝了!")
                else:
                    print(f"😢 你輸了! 對手 ({message['winner']}) 獲勝!")
            else:
                print(f"🤝 平局!")
            print(f"{'=' * 50}\n")
            print("遊戲結束，3秒後自動關閉...")
            import time
            time.sleep(3)
            self.running = False
        
        elif msg_type == 'error':
            print(f"\n❌ {message['message']}")
    
    def display_board(self):
        """Display the board"""
        print("\n" + "=" * 30)
        print("     井字遊戲 - 當前棋盤")
        print("=" * 30)
        print("\n     0   1   2")
        for i, row in enumerate(self.board):
            print(f"  {i}  ", end="")
            for j, cell in enumerate(row):
                display = cell if cell else ' '
                print(f" {display} ", end="")
                if j < 2:
                    print("|", end="")
            print()
            if i < 2:
                print("     " + "-" * 11)
        print()
    
    def make_move(self):
        """Get player's move"""
        while True:
            try:
                move = input(f"請輸入位置 (行 列，例如: 0 1): ").strip()
                if not move:
                    continue
                
                parts = move.split()
                if len(parts) != 2:
                    print("❌ 請輸入兩個數字 (行 列)")
                    continue
                
                row, col = int(parts[0]), int(parts[1])
                
                if row < 0 or row > 2 or col < 0 or col > 2:
                    print("❌ 位置必須在 0-2 之間")
                    continue
                
                if self.board[row][col] != '':
                    print("❌ 此位置已被佔據，請選擇其他位置")
                    continue
                
                # Send move to server
                self.send_message({
                    'type': 'move',
                    'row': row,
                    'col': col
                })
                break
            
            except ValueError:
                print("❌ 請輸入有效的數字")
            except KeyboardInterrupt:
                self.running = False
                break
    
    def send_message(self, message):
        """Send JSON message to server"""
        try:
            data = json.dumps(message).encode('utf-8')
            self.socket.sendall(len(data).to_bytes(4, 'big'))
            self.socket.sendall(data)
        except Exception as e:
            print(f"發送訊息失敗: {e}")
            self.running = False
    
    def recv_message(self):
        """Receive JSON message from server"""
        try:
            length_bytes = self.socket.recv(4)
            if not length_bytes:
                return None
            length = int.from_bytes(length_bytes, 'big')
            data = b''
            while len(data) < length:
                chunk = self.socket.recv(length - len(data))
                if not chunk:
                    return None
                data += chunk
            return json.loads(data.decode('utf-8'))
        except:
            return None
    
    def cleanup(self):
        """Cleanup resources"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Server: python game.py server [--port PORT]")
        print("  Client: python game.py client [--host HOST] [--port PORT]")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == "server":
        port = 5001
        for i, arg in enumerate(sys.argv):
            if arg == "--port" and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])
        
        server = TicTacToeServer(port=port)
        server.start()
    
    elif mode == "client":
        host = 'localhost'
        port = 5001
        
        for i, arg in enumerate(sys.argv):
            if arg == "--host" and i + 1 < len(sys.argv):
                host = sys.argv[i + 1]
            elif arg == "--port" and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])
        
        client = TicTacToeClient(host, port)
        client.run()
    
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
