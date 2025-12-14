"""
Snake Game - Enhanced Version 1.1.0
A single-player game for the Game Store platform

新功能：
- 難度選擇（簡單/中等/困難）
- 暫停/繼續功能 (按空白鍵)
- 改進的視覺效果
- 最高分記錄
- 遊戲說明顯示
"""

import tkinter as tk
import random
from tkinter import messagebox
import os
import json


class SnakeGame:
    def __init__(self, master):
        self.master = master
        self.master.title("貪食蛇 v1.1.0")
        self.master.resizable(False, False)
        
        # Game settings
        self.width = 400
        self.height = 400
        self.cell_size = 20
        
        # Difficulty settings
        self.difficulties = {
            'Easy': 150,
            'Medium': 100,
            'Hard': 60
        }
        self.difficulty = 'Medium'
        self.delay = self.difficulties[self.difficulty]
        
        # Game state
        self.snake = [(5, 5), (5, 4), (5, 3)]
        self.direction = 'Right'
        self.next_direction = 'Right'
        self.food = self.spawn_food()
        self.score = 0
        self.high_score = self.load_high_score()
        self.game_over = False
        self.paused = False
        self.game_started = False
        
        # UI Setup
        self.setup_ui()
        
        # Key bindings
        self.master.bind('<Up>', self.on_key_press)
        self.master.bind('<Down>', self.on_key_press)
        self.master.bind('<Left>', self.on_key_press)
        self.master.bind('<Right>', self.on_key_press)
        self.master.bind('<space>', self.toggle_pause)
        self.master.bind('r', self.restart_game)
        
        # Draw initial state
        self.draw()
    
    def setup_ui(self):
        """Setup user interface"""
        # Top frame for info
        top_frame = tk.Frame(self.master, bg='#2c3e50')
        top_frame.pack(fill=tk.X)
        
        # Score display
        self.score_label = tk.Label(
            top_frame,
            text=f'分數: {self.score}',
            font=('Arial', 14, 'bold'),
            bg='#2c3e50',
            fg='#ecf0f1'
        )
        self.score_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # High score display
        self.high_score_label = tk.Label(
            top_frame,
            text=f'最高分: {self.high_score}',
            font=('Arial', 14, 'bold'),
            bg='#2c3e50',
            fg='#f39c12'
        )
        self.high_score_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # Difficulty display
        self.difficulty_label = tk.Label(
            top_frame,
            text=f'難度: {self.difficulty}',
            font=('Arial', 12),
            bg='#2c3e50',
            fg='#3498db'
        )
        self.difficulty_label.pack(side=tk.RIGHT, padx=10, pady=5)
        
        # Game canvas
        self.canvas = tk.Canvas(
            self.master,
            width=self.width,
            height=self.height,
            bg='#34495e',
            highlightthickness=0
        )
        self.canvas.pack()
        
        # Bottom frame for controls
        bottom_frame = tk.Frame(self.master, bg='#2c3e50')
        bottom_frame.pack(fill=tk.X)
        
        # Instructions
        instructions = tk.Label(
            bottom_frame,
            text='方向鍵: 移動 | 空白鍵: 暫停 | R: 重新開始',
            font=('Arial', 10),
            bg='#2c3e50',
            fg='#95a5a6'
        )
        instructions.pack(pady=5)
        
        # Start game button
        self.start_button = tk.Button(
            bottom_frame,
            text='開始遊戲',
            command=self.start_game,
            bg='#27ae60',
            fg='white',
            font=('Arial', 16, 'bold'),
            padx=40,
            pady=10
        )
        self.start_button.pack(pady=10)
        
        # Difficulty buttons
        button_frame = tk.Frame(bottom_frame, bg='#2c3e50')
        button_frame.pack(pady=5)
        
        for diff in ['Easy', 'Medium', 'Hard']:
            btn = tk.Button(
                button_frame,
                text=diff,
                command=lambda d=diff: self.change_difficulty(d),
                bg='#3498db',
                fg='white',
                font=('Arial', 10),
                padx=10
            )
            btn.pack(side=tk.LEFT, padx=5)
    
    def start_game(self):
        """Start the game when button is clicked"""
        if not self.game_started and not self.game_over:
            self.game_started = True
            self.start_button.pack_forget()  # Hide start button
            self.update()
    
    def load_high_score(self):
        """Load high score from file"""
        try:
            if os.path.exists('high_score.json'):
                with open('high_score.json', 'r') as f:
                    data = json.load(f)
                    return data.get('high_score', 0)
        except:
            pass
        return 0
    
    def save_high_score(self):
        """Save high score to file"""
        try:
            with open('high_score.json', 'w') as f:
                json.dump({'high_score': self.high_score}, f)
        except:
            pass
    
    def change_difficulty(self, difficulty):
        """Change game difficulty"""
        if not self.game_over and len(self.snake) > 3:
            if not messagebox.askyesno("確認", "改變難度會重新開始遊戲，確定嗎？"):
                return
        
        self.difficulty = difficulty
        self.delay = self.difficulties[difficulty]
        self.difficulty_label.config(text=f'難度: {self.difficulty}')
        self.restart_game()
    
    def toggle_pause(self, event=None):
        """Toggle pause state"""
        if not self.game_started or self.game_over:
            return
        
        if not self.game_over:
            self.paused = not self.paused
            if self.paused:
                self.canvas.create_text(
                    self.width // 2,
                    self.height // 2,
                    text='暫停',
                    font=('Arial', 40, 'bold'),
                    fill='#e74c3c',
                    tags='pause'
                )
            else:
                self.canvas.delete('pause')
    
    def restart_game(self, event=None):
        """Restart the game"""
        self.snake = [(5, 5), (5, 4), (5, 3)]
        self.direction = 'Right'
        self.next_direction = 'Right'
        self.food = self.spawn_food()
        self.score = 0
        self.game_over = False
        self.paused = False
        self.game_started = False
        self.score_label.config(text=f'分數: {self.score}')
        self.canvas.delete('all')
        self.draw()
        # Show start button again
        self.start_button.pack(pady=10)
    
    def spawn_food(self):
        """Spawn food at random position"""
        while True:
            x = random.randint(0, self.width // self.cell_size - 1)
            y = random.randint(0, self.height // self.cell_size - 1)
            if (x, y) not in self.snake:
                return (x, y)
    
    def on_key_press(self, event):
        """Handle key press events"""
        if not self.game_started:
            return
        
        key = event.keysym
        
        # Prevent reversing
        if key == 'Up' and self.direction != 'Down':
            self.next_direction = 'Up'
        elif key == 'Down' and self.direction != 'Up':
            self.next_direction = 'Down'
        elif key == 'Left' and self.direction != 'Right':
            self.next_direction = 'Left'
        elif key == 'Right' and self.direction != 'Left':
            self.next_direction = 'Right'
    
    def move_snake(self):
        """Move the snake"""
        self.direction = self.next_direction
        head_x, head_y = self.snake[0]
        
        # Calculate new head position
        if self.direction == 'Up':
            new_head = (head_x, head_y - 1)
        elif self.direction == 'Down':
            new_head = (head_x, head_y + 1)
        elif self.direction == 'Left':
            new_head = (head_x - 1, head_y)
        elif self.direction == 'Right':
            new_head = (head_x + 1, head_y)
        
        # Check collision with walls
        if (new_head[0] < 0 or new_head[0] >= self.width // self.cell_size or
            new_head[1] < 0 or new_head[1] >= self.height // self.cell_size):
            self.game_over = True
            return
        
        # Check collision with self
        if new_head in self.snake:
            self.game_over = True
            return
        
        # Add new head
        self.snake.insert(0, new_head)
        
        # Check if food eaten
        if new_head == self.food:
            self.score += 10
            self.score_label.config(text=f'分數: {self.score}')
            
            # Update high score
            if self.score > self.high_score:
                self.high_score = self.score
                self.high_score_label.config(text=f'最高分: {self.high_score}')
                self.save_high_score()
            
            self.food = self.spawn_food()
        else:
            # Remove tail if no food eaten
            self.snake.pop()
    
    def draw(self):
        """Draw the game"""
        self.canvas.delete('all')
        
        # Draw grid (subtle)
        for i in range(0, self.width, self.cell_size):
            self.canvas.create_line(i, 0, i, self.height, fill='#2c3e50', width=1)
        for i in range(0, self.height, self.cell_size):
            self.canvas.create_line(0, i, self.width, i, fill='#2c3e50', width=1)
        
        # Draw snake with gradient effect
        for i, (x, y) in enumerate(self.snake):
            # Head is brighter
            if i == 0:
                color = '#2ecc71'  # Bright green
                self.canvas.create_oval(
                    x * self.cell_size + 2,
                    y * self.cell_size + 2,
                    (x + 1) * self.cell_size - 2,
                    (y + 1) * self.cell_size - 2,
                    fill=color,
                    outline='#27ae60',
                    width=2
                )
            else:
                # Body fades
                intensity = max(100, 255 - i * 5)
                color = f'#{intensity//2:02x}{intensity:02x}{intensity//2:02x}'
                self.canvas.create_rectangle(
                    x * self.cell_size + 2,
                    y * self.cell_size + 2,
                    (x + 1) * self.cell_size - 2,
                    (y + 1) * self.cell_size - 2,
                    fill=color,
                    outline=''
                )
        
        # Draw food (pulsing effect)
        fx, fy = self.food
        self.canvas.create_oval(
            fx * self.cell_size + 3,
            fy * self.cell_size + 3,
            (fx + 1) * self.cell_size - 3,
            (fy + 1) * self.cell_size - 3,
            fill='#e74c3c',
            outline='#c0392b',
            width=2
        )
        
        # Draw pause text if paused
        if self.paused:
            self.canvas.create_text(
                self.width // 2,
                self.height // 2,
                text='暫停',
                font=('Arial', 40, 'bold'),
                fill='#e74c3c',
                tags='pause'
            )
    
    def update(self):
        """Update game state"""
        if not self.game_over and not self.paused:
            self.move_snake()
            
            if self.game_over:
                # Write game result to file for lobby server
                try:
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    result = f"最終分數: {self.score} (難度: {self.difficulty})"
                    with open(os.path.join(script_dir, 'game_result.txt'), 'w', encoding='utf-8') as f:
                        f.write(result)
                    print(f"\n✅ 遊戲結果已寫入: {result}")
                except Exception as e:
                    print(f"⚠️  無法寫入遊戲結果: {e}")
                
                self.canvas.create_text(
                    self.width // 2,
                    self.height // 2 - 30,
                    text='遊戲結束',
                    font=('Arial', 30, 'bold'),
                    fill='#e74c3c'
                )
                self.canvas.create_text(
                    self.width // 2,
                    self.height // 2 + 20,
                    text=f'最終分數: {self.score}',
                    font=('Arial', 20),
                    fill='#ecf0f1'
                )
                self.canvas.create_text(
                    self.width // 2,
                    self.height // 2 + 50,
                    text='按 R 重新開始',
                    font=('Arial', 14),
                    fill='#95a5a6'
                )
                return
        
        self.draw()
        self.master.after(self.delay, self.update)


if __name__ == '__main__':
    root = tk.Tk()
    game = SnakeGame(root)
    root.mainloop()
