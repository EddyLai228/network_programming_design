"""
Snake Battle - GUI Multiplayer Game
Two players compete in a snake game
"""

import socket
import json
import sys
import os
import pygame
import random
from collections import deque

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 100, 255)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)

# Game settings
GRID_SIZE = 20
CELL_SIZE = 25
WINDOW_WIDTH = GRID_SIZE * CELL_SIZE
WINDOW_HEIGHT = GRID_SIZE * CELL_SIZE + 50  # Extra space for score


class SnakeBattleGame:
    def __init__(self):
        self.grid_size = GRID_SIZE
        self.reset_game()
    
    def reset_game(self):
        """Reset game state"""
        # Player 1 (Red) starts from left
        self.snake1 = deque([(5, 10), (4, 10), (3, 10)])
        self.direction1 = (1, 0)  # Moving right
        
        # Player 2 (Blue) starts from right
        self.snake2 = deque([(14, 10), (15, 10), (16, 10)])
        self.direction2 = (-1, 0)  # Moving left
        
        self.food = self.spawn_food()
        self.score1 = 0
        self.score2 = 0
        self.game_over = False
        self.winner = None
    
    def spawn_food(self):
        """Spawn food at random position"""
        while True:
            food = (random.randint(0, self.grid_size - 1), 
                   random.randint(0, self.grid_size - 1))
            if food not in self.snake1 and food not in self.snake2:
                return food
    
    def move_snake(self, player):
        """Move snake for specified player"""
        if player == 1:
            snake = self.snake1
            direction = self.direction1
        else:
            snake = self.snake2
            direction = self.direction2
        
        # Calculate new head position
        head = snake[0]
        new_head = ((head[0] + direction[0]) % self.grid_size,
                   (head[1] + direction[1]) % self.grid_size)
        
        # Check collision with itself or other snake
        if new_head in snake or new_head in (self.snake1 if player == 2 else self.snake2):
            self.game_over = True
            self.winner = 2 if player == 1 else 1
            return False
        
        # Add new head
        snake.appendleft(new_head)
        
        # Check if ate food
        if new_head == self.food:
            if player == 1:
                self.score1 += 1
            else:
                self.score2 += 1
            self.food = self.spawn_food()
        else:
            snake.pop()
        
        return True
    
    def update(self):
        """Update game state"""
        if not self.game_over:
            self.move_snake(1)
            if not self.game_over:
                self.move_snake(2)
    
    def change_direction(self, player, direction):
        """Change snake direction"""
        if player == 1:
            # Prevent reversing
            if (direction[0] * -1, direction[1] * -1) != self.direction1:
                self.direction1 = direction
        else:
            if (direction[0] * -1, direction[1] * -1) != self.direction2:
                self.direction2 = direction
    
    def get_state(self):
        """Get game state"""
        return {
            'snake1': list(self.snake1),
            'snake2': list(self.snake2),
            'food': self.food,
            'score1': self.score1,
            'score2': self.score2,
            'game_over': self.game_over,
            'winner': self.winner
        }


class SnakeBattleServer:
    def __init__(self, host='0.0.0.0', port=5001):
        self.host = host
        self.port = port
        self.game = SnakeBattleGame()
        self.players = {}
        self.running = True
    
    def start(self):
        """Start game server"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(2)
        
        print(f"Snake Battle Server started on {self.host}:{self.port}")
        print("Waiting for players...")
        
        # Accept two players
        for i in range(1, 3):
            client_socket, address = server_socket.accept()
            self.players[i] = client_socket
            print(f"Player {i} connected from {address}")
            
            self.send_message(client_socket, {
                'type': 'welcome',
                'player': i,
                'message': f'你是玩家 {i}'
            })
        
        print("\nGame started!")
        
        import time
        import select
        
        # Game loop
        last_update = time.time()
        update_interval = 0.15  # 150ms per frame
        
        while self.running and not self.game.game_over:
            current_time = time.time()
            
            # Check for player input
            for player_num, sock in self.players.items():
                ready = select.select([sock], [], [], 0)
                if ready[0]:
                    try:
                        data = self.recv_message(sock)
                        if data and data['type'] == 'direction':
                            direction = tuple(data['direction'])
                            self.game.change_direction(player_num, direction)
                    except:
                        pass
            
            # Update game state
            if current_time - last_update >= update_interval:
                self.game.update()
                self.broadcast_state()
                last_update = current_time
        
        # Game over
        state = self.game.get_state()
        winner_msg = f"玩家 {state['winner']} 獲勝！" if state['winner'] else "平局！"
        self.broadcast({
            'type': 'game_over',
            'state': state,
            'message': winner_msg
        })
        
        print(f"\n遊戲結束: {winner_msg}")
        
        # Write game result to file for lobby server
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            if state['winner'] == 1:
                result = f"玩家 1 (紅蛇) 獲勝! 分數: {state['score1']} vs {state['score2']}"
            elif state['winner'] == 2:
                result = f"玩家 2 (藍蛇) 獲勝! 分數: {state['score2']} vs {state['score1']}"
            else:
                result = "平局!"
            
            with open(os.path.join(script_dir, 'game_result.txt'), 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"✅ 遊戲結果已寫入: {result}")
        except Exception as e:
            print(f"⚠️  無法寫入遊戲結果: {e}")
        
        time.sleep(1)
        for sock in self.players.values():
            sock.close()
        server_socket.close()
    
    def broadcast_state(self):
        """Broadcast game state"""
        self.broadcast({
            'type': 'state',
            'state': self.game.get_state()
        })
    
    def broadcast(self, message):
        """Broadcast to all players"""
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
            sock.setblocking(False)
            length_bytes = sock.recv(4)
            if not length_bytes:
                return None
            length = int.from_bytes(length_bytes, 'big')
            sock.setblocking(True)
            data = sock.recv(length)
            return json.loads(data.decode('utf-8'))
        except:
            return None


class SnakeBattleClient:
    def __init__(self, host='localhost', port=5001):
        self.host = host
        self.port = port
        self.socket = None
        self.player = None
        self.running = True
        
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption('Snake Battle')
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
    
    def connect(self):
        """Connect to server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.socket.setblocking(False)
            
            # Receive welcome
            import time
            time.sleep(0.1)
            msg = self.recv_message()
            if msg and msg['type'] == 'welcome':
                self.player = msg['player']
                print(msg['message'])
                return True
        except Exception as e:
            print(f"連線失敗: {e}")
        return False
    
    def run(self):
        """Run game client"""
        if not self.connect():
            return
        
        print("\n控制說明:")
        print(f"  你是玩家 {self.player}")
        print("  控制: 方向鍵 或 W/A/S/D")
        print(f"  你的蛇顏色: {'紅色' if self.player == 1 else '藍色'}")
        
        while self.running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    direction = None
                    
                    # Both WASD and arrow keys work for all players
                    if event.key in (pygame.K_w, pygame.K_UP):
                        direction = (0, -1)
                    elif event.key in (pygame.K_s, pygame.K_DOWN):
                        direction = (0, 1)
                    elif event.key in (pygame.K_a, pygame.K_LEFT):
                        direction = (-1, 0)
                    elif event.key in (pygame.K_d, pygame.K_RIGHT):
                        direction = (1, 0)
                    
                    if direction:
                        self.send_message({
                            'type': 'direction',
                            'direction': direction
                        })
            
            # Receive state updates
            msg = self.recv_message()
            if msg:
                if msg['type'] == 'state':
                    self.render(msg['state'])
                elif msg['type'] == 'game_over':
                    self.render(msg['state'])
                    self.show_game_over(msg['message'])
                    
                    pygame.time.wait(3000)
                    self.running = False
            
            self.clock.tick(60)
        
        pygame.quit()
        self.socket.close()
    
    def render(self, state):
        """Render game state"""
        self.screen.fill(BLACK)
        
        # Draw grid
        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE - 1, CELL_SIZE - 1)
                pygame.draw.rect(self.screen, (20, 20, 20), rect)
        
        # Draw snake 1 (Red)
        for segment in state['snake1']:
            rect = pygame.Rect(segment[0] * CELL_SIZE, segment[1] * CELL_SIZE, 
                             CELL_SIZE - 2, CELL_SIZE - 2)
            pygame.draw.rect(self.screen, RED, rect)
        
        # Draw snake 2 (Blue)
        for segment in state['snake2']:
            rect = pygame.Rect(segment[0] * CELL_SIZE, segment[1] * CELL_SIZE, 
                             CELL_SIZE - 2, CELL_SIZE - 2)
            pygame.draw.rect(self.screen, BLUE, rect)
        
        # Draw food
        food_rect = pygame.Rect(state['food'][0] * CELL_SIZE, state['food'][1] * CELL_SIZE,
                               CELL_SIZE - 2, CELL_SIZE - 2)
        pygame.draw.rect(self.screen, YELLOW, food_rect)
        
        # Draw scores
        score_text = f"P1: {state['score1']}  P2: {state['score2']}"
        text_surface = self.font.render(score_text, True, WHITE)
        self.screen.blit(text_surface, (10, WINDOW_HEIGHT - 40))
        
        pygame.display.flip()
    
    def show_game_over(self, message):
        """Show game over message"""
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        overlay.set_alpha(128)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))
        
        text = self.font.render(message, True, WHITE)
        text_rect = text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        self.screen.blit(text, text_rect)
        
        pygame.display.flip()
    
    def send_message(self, message):
        """Send message to server"""
        try:
            data = json.dumps(message).encode('utf-8')
            self.socket.sendall(len(data).to_bytes(4, 'big') + data)
        except:
            pass
    
    def recv_message(self):
        """Receive message from server"""
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
        
        server = SnakeBattleServer(port=port)
        server.start()
    
    elif mode == "client":
        host = 'localhost'
        port = 5001
        
        for i, arg in enumerate(sys.argv):
            if arg == "--host" and i + 1 < len(sys.argv):
                host = sys.argv[i + 1]
            elif arg == "--port" and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])
        
        client = SnakeBattleClient(host, port)
        client.run()
    
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
