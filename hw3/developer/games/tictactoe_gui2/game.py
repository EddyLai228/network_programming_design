"""
Tic-Tac-Toe GUI - Multiplayer Game
A GUI version of tic-tac-toe for two players over network
"""

import socket
import json
import sys
import os
import tkinter as tk
from tkinter import messagebox
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
        return all(self.board[i][j] != '' for i in range(3) for j in range(3))
    
    def get_state(self):
        """Get game state"""
        return {
            'board': self.board,
            'current_player': self.current_player,
            'game_over': self.game_over,
            'winner': self.winner
        }


class TicTacToeServer:
    def __init__(self, port=5001):
        self.port = port
        self.game = TicTacToeGame()
        self.players = {}  # symbol -> socket
        self.player_symbols = ['X', 'O']
    
    def start(self):
        """Start the game server"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', self.port))
        server_socket.listen(2)
        
        print(f"井字遊戲伺服器啟動於端口 {self.port}")
        print("等待玩家連線...")
        
        # Accept two players
        for symbol in self.player_symbols:
            client_socket, address = server_socket.accept()
            self.players[symbol] = client_socket
            print(f"玩家 {symbol} 已連線 ({address})")
            
            self.send_message(client_socket, {
                'type': 'welcome',
                'symbol': symbol,
                'message': f'歡迎！你是玩家 {symbol}'
            })
        
        print("遊戲開始！")
        self.broadcast_state()
        
        # Game loop
        while not self.game.game_over:
            current_symbol = self.game.current_player
            current_socket = self.players[current_symbol]
            
            # Notify current player
            self.send_message(current_socket, {
                'type': 'your_turn',
                'message': f'輪到你了！(你是 {current_symbol})'
            })
            
            # Wait for move
            try:
                msg = self.recv_message(current_socket)
                if not msg or msg['type'] != 'move':
                    continue
                
                row, col = msg['row'], msg['col']
                success, message = self.game.make_move(row, col, current_symbol)
                
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


class TicTacToeClientGUI:
    def __init__(self, master, host='localhost', port=5001):
        self.master = master
        self.host = host
        self.port = port
        self.socket = None
        self.symbol = None
        self.board = [['' for _ in range(3)] for _ in range(3)]
        self.my_turn = False
        
        self.master.title("井字遊戲 - 雙人對戰")
        self.master.resizable(False, False)
        self.master.configure(bg='#2c3e50')
        
        # Colors
        self.bg_color = '#34495e'
        self.x_color = '#e74c3c'
        self.o_color = '#3498db'
        
        # Setup UI
        self.setup_ui()
        
        # Connect to server
        self.connect()
        
        # Start receiving messages
        self.running = True
        receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        receive_thread.start()
    
    def setup_ui(self):
        """Setup user interface"""
        # Title
        self.title_label = tk.Label(
            self.master,
            text='井字遊戲 - 連線中...',
            font=('Arial', 20, 'bold'),
            bg='#2c3e50',
            fg='#ecf0f1'
        )
        self.title_label.pack(pady=10)
        
        # Status
        self.status_label = tk.Label(
            self.master,
            text='等待連線...',
            font=('Arial', 14),
            bg='#2c3e50',
            fg='#ecf0f1'
        )
        self.status_label.pack(pady=5)
        
        # Game board
        board_frame = tk.Frame(self.master, bg='#2c3e50')
        board_frame.pack(pady=10)
        
        self.buttons = []
        for i in range(3):
            row = []
            for j in range(3):
                btn = tk.Button(
                    board_frame,
                    text='',
                    font=('Arial', 36, 'bold'),
                    width=4,
                    height=2,
                    bg=self.bg_color,
                    fg='#ecf0f1',
                    activebackground='#576574',
                    command=lambda r=i, c=j: self.make_move(r, c),
                    state='disabled',
                    relief=tk.RAISED,
                    bd=3
                )
                btn.grid(row=i, column=j, padx=2, pady=2)
                row.append(btn)
            self.buttons.append(row)
    
    def connect(self):
        """Connect to game server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print(f"已連接到伺服器 {self.host}:{self.port}")
        except Exception as e:
            messagebox.showerror("連線錯誤", f"無法連接到遊戲伺服器: {e}")
            self.master.quit()
    
    def make_move(self, row, col):
        """Make a move"""
        if not self.my_turn:
            return
        
        if self.board[row][col] != '':
            return
        
        # Send move to server
        self.send_message({
            'type': 'move',
            'row': row,
            'col': col
        })
        
        self.my_turn = False
        self.update_buttons_state()
    
    def receive_messages(self):
        """Receive messages from server"""
        while self.running:
            try:
                msg = self.recv_message()
                if not msg:
                    break
                
                self.handle_message(msg)
            except Exception as e:
                print(f"接收訊息錯誤: {e}")
                break
    
    def handle_message(self, msg):
        """Handle message from server"""
        msg_type = msg['type']
        
        if msg_type == 'welcome':
            self.symbol = msg['symbol']
            self.title_label.config(text=f'井字遊戲 - 你是 {self.symbol}')
            self.status_label.config(text=msg['message'])
        
        elif msg_type == 'state':
            state = msg['state']
            self.board = state['board']
            self.update_board()
            
            if not state['game_over']:
                if state['current_player'] == self.symbol:
                    self.status_label.config(
                        text=f'輪到你了！(你是 {self.symbol})',
                        fg='#27ae60'
                    )
                else:
                    self.status_label.config(
                        text=f'等待對手...',
                        fg='#f39c12'
                    )
        
        elif msg_type == 'your_turn':
            self.my_turn = True
            self.update_buttons_state()
            self.status_label.config(
                text=f'輪到你了！(你是 {self.symbol})',
                fg='#27ae60'
            )
        
        elif msg_type == 'error':
            messagebox.showerror("錯誤", msg['message'])
        
        elif msg_type == 'game_over':
            self.update_board()
            self.status_label.config(
                text=msg['message'],
                fg='#e74c3c' if msg.get('winner') != self.symbol else '#27ae60'
            )
            messagebox.showinfo("遊戲結束", msg['message'])
            self.running = False
    
    def update_board(self):
        """Update board display"""
        for i in range(3):
            for j in range(3):
                cell = self.board[i][j]
                if cell != '':
                    color = self.x_color if cell == 'X' else self.o_color
                    self.buttons[i][j].config(
                        text=cell,
                        fg=color,
                        state='disabled'
                    )
    
    def update_buttons_state(self):
        """Update button states based on turn"""
        for i in range(3):
            for j in range(3):
                if self.board[i][j] == '':
                    state = 'normal' if self.my_turn else 'disabled'
                    self.buttons[i][j].config(state=state)
    
    def send_message(self, message):
        """Send JSON message"""
        try:
            data = json.dumps(message).encode('utf-8')
            self.socket.sendall(len(data).to_bytes(4, 'big') + data)
        except Exception as e:
            print(f"發送訊息錯誤: {e}")
    
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
        
        root = tk.Tk()
        client = TicTacToeClientGUI(root, host, port)
        root.mainloop()
    
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
