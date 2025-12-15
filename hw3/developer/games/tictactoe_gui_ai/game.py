"""
Tic-Tac-Toe GUI - Single Player Game
A GUI version of the classic tic-tac-toe game with AI opponent
"""

import tkinter as tk
from tkinter import messagebox
import random
import os


class TicTacToeGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("井字遊戲 (Tic-Tac-Toe)")
        self.master.resizable(False, False)
        self.master.configure(bg='#2c3e50')
        
        # Game state
        self.board = [['' for _ in range(3)] for _ in range(3)]
        self.current_player = 'X'  # X is human, O is AI
        self.game_over = False
        self.winner = None
        self.game_started = False
        
        # Colors
        self.bg_color = '#34495e'
        self.x_color = '#e74c3c'
        self.o_color = '#3498db'
        self.win_color = '#f39c12'
        
        # UI Setup
        self.setup_ui()
    
    def setup_ui(self):
        """Setup user interface"""
        # Title
        title_label = tk.Label(
            self.master,
            text='井字遊戲',
            font=('Arial', 24, 'bold'),
            bg='#2c3e50',
            fg='#ecf0f1'
        )
        title_label.pack(pady=10)
        
        # Info frame
        info_frame = tk.Frame(self.master, bg='#2c3e50')
        info_frame.pack(pady=5)
        
        self.status_label = tk.Label(
            info_frame,
            text='點擊「開始遊戲」來開始',
            font=('Arial', 14),
            bg='#2c3e50',
            fg='#ecf0f1'
        )
        self.status_label.pack()
        
        # Game board frame
        board_frame = tk.Frame(self.master, bg='#2c3e50')
        board_frame.pack(pady=10)
        
        # Create 3x3 grid of buttons
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
        
        # Control buttons frame
        control_frame = tk.Frame(self.master, bg='#2c3e50')
        control_frame.pack(pady=10)
        
        # Start button
        self.start_button = tk.Button(
            control_frame,
            text='開始遊戲',
            font=('Arial', 14, 'bold'),
            bg='#27ae60',
            fg='white',
            activebackground='#229954',
            command=self.start_game,
            padx=20,
            pady=10,
            relief=tk.RAISED,
            bd=3
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        # Restart button
        self.restart_button = tk.Button(
            control_frame,
            text='重新開始',
            font=('Arial', 14, 'bold'),
            bg='#3498db',
            fg='white',
            activebackground='#2980b9',
            command=self.restart_game,
            padx=20,
            pady=10,
            relief=tk.RAISED,
            bd=3,
            state='disabled'
        )
        self.restart_button.pack(side=tk.LEFT, padx=5)
        
        # Info label
        info_label = tk.Label(
            self.master,
            text='你是 X，電腦是 O',
            font=('Arial', 12),
            bg='#2c3e50',
            fg='#95a5a6'
        )
        info_label.pack(pady=5)
    
    def start_game(self):
        """Start the game"""
        self.game_started = True
        self.start_button.config(state='disabled')
        self.restart_button.config(state='normal')
        
        # Enable all buttons
        for i in range(3):
            for j in range(3):
                self.buttons[i][j].config(state='normal')
        
        self.status_label.config(text='你的回合 (X)')
    
    def make_move(self, row, col):
        """Make a move on the board"""
        if not self.game_started or self.game_over:
            return
        
        if self.board[row][col] != '':
            return
        
        # Player move
        self.board[row][col] = 'X'
        self.buttons[row][col].config(
            text='X',
            fg=self.x_color,
            state='disabled'
        )
        
        # Check if player won
        if self.check_winner('X'):
            self.end_game('X')
            return
        
        # Check for draw
        if self.is_board_full():
            self.end_game(None)
            return
        
        # AI move
        self.status_label.config(text='電腦思考中...')
        self.master.update()
        self.master.after(500, self.ai_move)
    
    def ai_move(self):
        """AI makes a move"""
        # Simple AI: try to win, block player, or random
        move = self.get_best_move()
        
        if move:
            row, col = move
            self.board[row][col] = 'O'
            self.buttons[row][col].config(
                text='O',
                fg=self.o_color,
                state='disabled'
            )
            
            # Check if AI won
            if self.check_winner('O'):
                self.end_game('O')
                return
            
            # Check for draw
            if self.is_board_full():
                self.end_game(None)
                return
            
            self.status_label.config(text='你的回合 (X)')
    
    def get_best_move(self):
        """Get the best move for AI"""
        # 1. Try to win
        for i in range(3):
            for j in range(3):
                if self.board[i][j] == '':
                    self.board[i][j] = 'O'
                    if self.check_winner('O'):
                        self.board[i][j] = ''
                        return (i, j)
                    self.board[i][j] = ''
        
        # 2. Block player from winning
        for i in range(3):
            for j in range(3):
                if self.board[i][j] == '':
                    self.board[i][j] = 'X'
                    if self.check_winner('X'):
                        self.board[i][j] = ''
                        return (i, j)
                    self.board[i][j] = ''
        
        # 3. Take center if available
        if self.board[1][1] == '':
            return (1, 1)
        
        # 4. Take a corner
        corners = [(0, 0), (0, 2), (2, 0), (2, 2)]
        random.shuffle(corners)
        for corner in corners:
            if self.board[corner[0]][corner[1]] == '':
                return corner
        
        # 5. Take any available space
        for i in range(3):
            for j in range(3):
                if self.board[i][j] == '':
                    return (i, j)
        
        return None
    
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
    
    def end_game(self, winner):
        """End the game"""
        self.game_over = True
        self.winner = winner
        
        # Disable all buttons
        for i in range(3):
            for j in range(3):
                self.buttons[i][j].config(state='disabled')
        
        # Determine result message
        if winner == 'X':
            result_msg = '你贏了！'
            self.status_label.config(text='🎉 你贏了！', fg='#27ae60')
        elif winner == 'O':
            result_msg = '電腦贏了！'
            self.status_label.config(text='電腦贏了！', fg='#e74c3c')
        else:
            result_msg = '平局！'
            self.status_label.config(text='平局！', fg='#f39c12')
        
        # Write game result to file for lobby server
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(script_dir, 'game_result.txt'), 'w', encoding='utf-8') as f:
                f.write(result_msg)
            print(f"\n✅ 遊戲結果已寫入: {result_msg}")
        except Exception as e:
            print(f"⚠️  無法寫入遊戲結果: {e}")
        
        # Show message box
        messagebox.showinfo("遊戲結束", result_msg)
    
    def restart_game(self):
        """Restart the game"""
        self.board = [['' for _ in range(3)] for _ in range(3)]
        self.current_player = 'X'
        self.game_over = False
        self.winner = None
        self.game_started = True
        
        # Reset all buttons
        for i in range(3):
            for j in range(3):
                self.buttons[i][j].config(
                    text='',
                    state='normal',
                    bg=self.bg_color
                )
        
        self.status_label.config(text='你的回合 (X)', fg='#ecf0f1')


def main():
    root = tk.Tk()
    game = TicTacToeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
