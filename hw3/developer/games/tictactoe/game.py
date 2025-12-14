"""
Tic-Tac-Toe - Simple CLI Game
A two-player game for the Game Store platform
"""

import socket
import json
import sys
import os


class TicTacToeGame:
    def __init__(self):
        self.board = [[' ' for _ in range(3)] for _ in range(3)]
        self.current_player = 'X'
        self.game_over = False
        self.winner = None
    
    def print_board(self):
        """Print the game board"""
        print("\n  0   1   2")
        for i, row in enumerate(self.board):
            print(f"{i} {' | '.join(row)}")
            if i < 2:
                print("  " + "-" * 11)
        print()
    
    def make_move(self, row, col):
        """Make a move on the board"""
        if row < 0 or row > 2 or col < 0 or col > 2:
            return False, "座標超出範圍"
        
        if self.board[row][col] != ' ':
            return False, "此位置已被佔據"
        
        self.board[row][col] = self.current_player
        
        # Check win
        if self.check_win():
            self.game_over = True
            self.winner = self.current_player
            return True, f"玩家 {self.current_player} 獲勝!"
        
        # Check draw
        if self.is_full():
            self.game_over = True
            return True, "平局!"
        
        # Switch player
        self.current_player = 'O' if self.current_player == 'X' else 'X'
        return True, "移動成功"
    
    def check_win(self):
        """Check if current player has won"""
        player = self.current_player
        
        # Check rows
        for row in self.board:
            if all(cell == player for cell in row):
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
    
    def is_full(self):
        """Check if board is full"""
        return all(cell != ' ' for row in self.board for cell in row)
    
    def get_state(self):
        """Get game state"""
        return {
            'board': self.board,
            'current_player': self.current_player,
            'game_over': self.game_over,
            'winner': self.winner
        }


class TicTacToeServer:
    def __init__(self, host='0.0.0.0', port=5001):
        self.host = host
        self.port = port
        self.game = TicTacToeGame()
        self.players = {}
        self.player_symbols = {}
    
    def start(self):
        """Start the game server"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(2)
        
        print(f"Tic-Tac-Toe Server started on {self.host}:{self.port}")
        print("Waiting for players...")
        
        # Accept two players
        for i, symbol in enumerate(['X', 'O']):
            client_socket, address = server_socket.accept()
            self.players[symbol] = client_socket
            self.player_symbols[client_socket] = symbol
            print(f"Player {symbol} connected from {address}")
            
            # Send welcome message
            self.send_message(client_socket, {
                'type': 'welcome',
                'symbol': symbol,
                'message': f'你是玩家 {symbol}'
            })
        
        # Start game loop
        print("\nGame started!")
        self.broadcast_state()
        
        while not self.game.game_over:
            current_socket = self.players[self.game.current_player]
            
            # Request move from current player
            self.send_message(current_socket, {
                'type': 'your_turn',
                'message': '輪到你了'
            })
            
            # Receive move
            try:
                data = self.recv_message(current_socket)
                if not data:
                    print(f"Player {self.game.current_player} disconnected")
                    break
                
                if data['type'] == 'move':
                    row = data['row']
                    col = data['col']
                    
                    success, message = self.game.make_move(row, col)
                    
                    if success:
                        self.broadcast_state()
                    else:
                        self.send_message(current_socket, {
                            'type': 'error',
                            'message': message
                        })
            except Exception as e:
                print(f"Error: {e}")
                break
        
        # Game over
        if self.game.winner:
            result_msg = f'玩家 {self.game.winner} 獲勝!'
            self.broadcast({
                'type': 'game_over',
                'winner': self.game.winner,
                'message': result_msg
            })
        else:
            result_msg = '平局!'
            self.broadcast({
                'type': 'game_over',
                'winner': None,
                'message': result_msg
            })
        
        # Write game result to file for lobby server
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(script_dir, 'game_result.txt'), 'w', encoding='utf-8') as f:
                f.write(result_msg)
            print(f"\n✅ 遊戲結果已寫入: {result_msg}")
        except Exception as e:
            print(f"⚠️  無法寫入遊戲結果: {e}")
        
        # Clean up
        for sock in self.players.values():
            sock.close()
        server_socket.close()
    
    def broadcast_state(self):
        """Broadcast game state to all players"""
        state = self.game.get_state()
        self.broadcast({
            'type': 'state',
            'state': state
        })
    
    def broadcast(self, message):
        """Broadcast message to all players"""
        for sock in self.players.values():
            self.send_message(sock, message)
    
    def send_message(self, sock, message):
        """Send JSON message"""
        try:
            data = json.dumps(message).encode('utf-8')
            sock.sendall(len(data).to_bytes(4, 'big') + data)
        except:
            pass
    
    def recv_message(self, sock):
        """Receive JSON message"""
        try:
            length_bytes = sock.recv(4)
            if not length_bytes:
                return None
            length = int.from_bytes(length_bytes, 'big')
            data = sock.recv(length)
            return json.loads(data.decode('utf-8'))
        except:
            return None


class TicTacToeClient:
    def __init__(self, host='localhost', port=5001):
        self.host = host
        self.port = port
        self.socket = None
        self.symbol = None
        self.board = [[' ' for _ in range(3)] for _ in range(3)]
    
    def connect(self):
        """Connect to game server"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        
        # Receive welcome message
        msg = self.recv_message()
        if msg and msg['type'] == 'welcome':
            self.symbol = msg['symbol']
            print(msg['message'])
            return True
        return False
    
    def run(self):
        """Run game client"""
        if not self.connect():
            print("連線失敗")
            return
        
        print("\n=== Tic-Tac-Toe ===")
        print("輸入格式: row col (例如: 0 1)")
        
        while True:
            msg = self.recv_message()
            if not msg:
                break
            
            if msg['type'] == 'state':
                state = msg['state']
                self.board = state['board']
                self.print_board()
                
                if state['game_over']:
                    continue
                
                print(f"當前玩家: {state['current_player']}")
            
            elif msg['type'] == 'your_turn':
                print(f"\n{msg['message']} (你是 {self.symbol})")
                
                while True:
                    try:
                        move = input("請輸入座標 (row col): ").strip().split()
                        if len(move) != 2:
                            print("格式錯誤，請輸入兩個數字")
                            continue
                        
                        row, col = int(move[0]), int(move[1])
                        
                        self.send_message({
                            'type': 'move',
                            'row': row,
                            'col': col
                        })
                        break
                    except ValueError:
                        print("請輸入有效的數字")
                    except KeyboardInterrupt:
                        print("\n遊戲中斷")
                        self.socket.close()
                        return
            
            elif msg['type'] == 'error':
                print(f"錯誤: {msg['message']}")
            
            elif msg['type'] == 'game_over':
                self.print_board()
                print(f"\n遊戲結束: {msg['message']}")
                break
        
        self.socket.close()
    
    def print_board(self):
        """Print the game board"""
        print("\n  0   1   2")
        for i, row in enumerate(self.board):
            print(f"{i} {' | '.join(row)}")
            if i < 2:
                print("  " + "-" * 11)
        print()
    
    def send_message(self, message):
        """Send JSON message"""
        data = json.dumps(message).encode('utf-8')
        self.socket.sendall(len(data).to_bytes(4, 'big') + data)
    
    def recv_message(self):
        """Receive JSON message"""
        try:
            length_bytes = self.socket.recv(4)
            if not length_bytes:
                return None
            length = int.from_bytes(length_bytes, 'big')
            data = self.socket.recv(length)
            return json.loads(data.decode('utf-8'))
        except:
            return None


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
