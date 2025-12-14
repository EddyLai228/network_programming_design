"""
Snake Game - Simple GUI Game
A single-player game for the Game Store platform
"""

import tkinter as tk
import random
from tkinter import messagebox


class SnakeGame:
    def __init__(self, master):
        self.master = master
        self.master.title("貪食蛇")
        self.master.resizable(False, False)
        
        # Game settings
        self.width = 400
        self.height = 400
        self.cell_size = 20
        self.delay = 100
        
        # Game state
        self.snake = [(5, 5), (5, 4), (5, 3)]
        self.direction = 'Right'
        self.next_direction = 'Right'
        self.food = self.spawn_food()
        self.score = 0
        self.game_over = False
        self.game_started = False
        
        # UI
        self.canvas = tk.Canvas(
            master,
            width=self.width,
            height=self.height,
            bg='black'
        )
        self.canvas.pack()
        
        self.score_label = tk.Label(
            master,
            text=f'分數: {self.score}',
            font=('Arial', 14)
        )
        self.score_label.pack()
        
        # Start button
        self.start_button = tk.Button(
            master,
            text='開始遊戲',
            font=('Arial', 14),
            command=self.start_game,
            bg='#4CAF50',
            fg='white',
            padx=20,
            pady=10
        )
        self.start_button.pack(pady=10)
        
        # Key bindings
        self.master.bind('<Up>', self.on_key_press)
        self.master.bind('<Down>', self.on_key_press)
        self.master.bind('<Left>', self.on_key_press)
        self.master.bind('<Right>', self.on_key_press)
        
        # Draw initial state
        self.draw()
    
    def start_game(self):
        """Start the game when button is clicked"""
        if not self.game_started:
            self.game_started = True
            self.start_button.pack_forget()  # Hide start button
            self.update()
    
    def spawn_food(self):
        """Spawn food at random position"""
        while True:
            x = random.randint(0, self.width // self.cell_size - 1)
            y = random.randint(0, self.height // self.cell_size - 1)
            if (x, y) not in self.snake:
                return (x, y)
    
    def on_key_press(self, event):
        """Handle key press"""
        if not self.game_started:
            return
        
        key = event.keysym
        
        # Prevent reverse direction
        if key == 'Up' and self.direction != 'Down':
            self.next_direction = 'Up'
        elif key == 'Down' and self.direction != 'Up':
            self.next_direction = 'Down'
        elif key == 'Left' and self.direction != 'Right':
            self.next_direction = 'Left'
        elif key == 'Right' and self.direction != 'Left':
            self.next_direction = 'Right'
    
    def update(self):
        """Update game state"""
        if self.game_over:
            return
        
        # Update direction
        self.direction = self.next_direction
        
        # Move snake
        head_x, head_y = self.snake[0]
        
        if self.direction == 'Up':
            new_head = (head_x, head_y - 1)
        elif self.direction == 'Down':
            new_head = (head_x, head_y + 1)
        elif self.direction == 'Left':
            new_head = (head_x - 1, head_y)
        else:  # Right
            new_head = (head_x + 1, head_y)
        
        # Check collision with walls
        if (new_head[0] < 0 or new_head[0] >= self.width // self.cell_size or
            new_head[1] < 0 or new_head[1] >= self.height // self.cell_size):
            self.end_game()
            return
        
        # Check collision with self
        if new_head in self.snake:
            self.end_game()
            return
        
        # Add new head
        self.snake.insert(0, new_head)
        
        # Check if ate food
        if new_head == self.food:
            self.score += 10
            self.score_label.config(text=f'分數: {self.score}')
            self.food = self.spawn_food()
            
            # Speed up slightly
            self.delay = max(50, self.delay - 1)
        else:
            # Remove tail
            self.snake.pop()
        
        # Redraw
        self.draw()
        
        # Schedule next update
        self.master.after(self.delay, self.update)
    
    def draw(self):
        """Draw game state"""
        self.canvas.delete('all')
        
        # Draw snake
        for i, (x, y) in enumerate(self.snake):
            color = '#00ff00' if i == 0 else '#00aa00'
            self.canvas.create_rectangle(
                x * self.cell_size,
                y * self.cell_size,
                (x + 1) * self.cell_size,
                (y + 1) * self.cell_size,
                fill=color,
                outline='black'
            )
        
        # Draw food
        x, y = self.food
        self.canvas.create_oval(
            x * self.cell_size + 2,
            y * self.cell_size + 2,
            (x + 1) * self.cell_size - 2,
            (y + 1) * self.cell_size - 2,
            fill='red',
            outline='darkred'
        )
    
    def end_game(self):
        """End the game"""
        self.game_over = True
        
        # Write game result to file for lobby server
        try:
            import os
            script_dir = os.path.dirname(os.path.abspath(__file__))
            result = f"最終分數: {self.score}"
            with open(os.path.join(script_dir, 'game_result.txt'), 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"\n✅ 遊戲結果已寫入: {result}")
        except Exception as e:
            print(f"⚠️  無法寫入遊戲結果: {e}")
        
        messagebox.showinfo(
            "遊戲結束",
            f"遊戲結束！\n最終分數: {self.score}"
        )
        self.master.quit()


def main():
    root = tk.Tk()
    game = SnakeGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
