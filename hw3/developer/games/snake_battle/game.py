"""
Snake Battle - Multiplayer Snake Game
Client-Server Architecture with Authoritative Server
"""

import pygame
import socket
import json
import sys
import threading
import time
import random

# Constants
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 800
CELL_SIZE = 20
GRID_WIDTH = WINDOW_WIDTH // CELL_SIZE
GRID_HEIGHT = WINDOW_HEIGHT // CELL_SIZE
FPS = 10

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)
GRAY = (128, 128, 128)

# Directions
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)


class GameServer:
    """Authoritative server - single source of truth"""
    def __init__(self):
        self.state = {
            'started': False,
            'over': False,
            'winner': None,
            'player1': {
                'snake': [(5, 10), (4, 10), (3, 10)],  # Left side, facing right
                'direction': RIGHT,
                'alive': True,
                'score': 0,
                'fire_cooldown': 0,
                'fires': []
            },
            'player2': {
                'snake': [(34, 30), (35, 30), (36, 30)],  # Right side, facing left
                'direction': LEFT,
                'alive': True,
                'score': 0,
                'fire_cooldown': 0,
                'fires': []
            },
            'food': (20, 20)
        }
        self.clients = {}
        self.running = True
    
    def spawn_food(self):
        """Spawn food avoiding snakes"""
        while True:
            pos = (random.randint(0, GRID_WIDTH - 1), random.randint(0, GRID_HEIGHT - 1))
            if (pos not in self.state['player1']['snake'] and 
                pos not in self.state['player2']['snake']):
                return pos
    
    def handle_input(self, player_id, data):
        """Process client input"""
        if 'start' in data and not self.state['started']:
            self.state['started'] = True
            return
        
        player = self.state[player_id]
        
        # Direction change
        if 'direction' in data:
            new_dir = tuple(data['direction'])
            old_dir = player['direction']
            # Prevent 180 degree turn
            if not (new_dir[0] == -old_dir[0] and new_dir[1] == -old_dir[1]):
                player['direction'] = new_dir
        
        # Fire
        if data.get('fire') and player['fire_cooldown'] == 0:
            player['fires'].append({
                'pos': list(player['snake'][0]),
                'dir': list(player['direction']),
                'life': 20
            })
            player['fire_cooldown'] = 30
    
    def update(self):
        """Update game logic - ONLY on server"""
        if not self.state['started'] or self.state['over']:
            return
        
        # Update fires
        for pid in ['player1', 'player2']:
            p = self.state[pid]
            if p['fire_cooldown'] > 0:
                p['fire_cooldown'] -= 1
            
            new_fires = []
            for fire in p['fires']:
                fire['pos'][0] += fire['dir'][0]
                fire['pos'][1] += fire['dir'][1]
                fire['life'] -= 1
                
                # Check bounds
                if not (0 <= fire['pos'][0] < GRID_WIDTH and 0 <= fire['pos'][1] < GRID_HEIGHT):
                    continue
                
                # Check hit opponent
                opp = 'player2' if pid == 'player1' else 'player1'
                if tuple(fire['pos']) in self.state[opp]['snake']:
                    self.state[opp]['alive'] = False
                    continue
                
                if fire['life'] > 0:
                    new_fires.append(fire)
            
            p['fires'] = new_fires
        
        # Update snakes
        for pid in ['player1', 'player2']:
            p = self.state[pid]
            if not p['alive']:
                continue
            
            # New head position
            head = p['snake'][0]
            new_head = (head[0] + p['direction'][0], head[1] + p['direction'][1])
            
            # Check collisions
            if not (0 <= new_head[0] < GRID_WIDTH and 0 <= new_head[1] < GRID_HEIGHT):
                p['alive'] = False
                continue
            
            if new_head in p['snake']:
                p['alive'] = False
                continue
            
            opp = 'player2' if pid == 'player1' else 'player1'
            if new_head in self.state[opp]['snake']:
                p['alive'] = False
                continue
            
            # Move
            p['snake'].insert(0, new_head)
            
            # Check food
            if new_head == self.state['food']:
                p['score'] += 10
                # Grow 3x
                p['snake'].extend([p['snake'][-1]] * 2)
                self.state['food'] = self.spawn_food()
            else:
                p['snake'].pop()
        
        # Check game over
        if not self.state['player1']['alive'] or not self.state['player2']['alive']:
            self.state['over'] = True
            if not self.state['player1']['alive'] and not self.state['player2']['alive']:
                self.state['winner'] = 'Draw'
            else:
                self.state['winner'] = 'Player 1' if self.state['player1']['alive'] else 'Player 2'
    
    def get_state(self):
        """Serialize state for network"""
        return {
            'started': self.state['started'],
            'over': self.state['over'],
            'winner': self.state['winner'],
            'player1': {
                'snake': self.state['player1']['snake'],
                'direction': list(self.state['player1']['direction']),
                'alive': self.state['player1']['alive'],
                'score': self.state['player1']['score'],
                'fire_cooldown': self.state['player1']['fire_cooldown'],
                'fires': self.state['player1']['fires']
            },
            'player2': {
                'snake': self.state['player2']['snake'],
                'direction': list(self.state['player2']['direction']),
                'alive': self.state['player2']['alive'],
                'score': self.state['player2']['score'],
                'fire_cooldown': self.state['player2']['fire_cooldown'],
                'fires': self.state['player2']['fires']
            },
            'food': self.state['food']
        }
    
    def broadcast(self):
        """Send state to all clients"""
        msg = json.dumps(self.get_state()) + '\n'
        for sock in self.clients.values():
            try:
                sock.sendall(msg.encode())
            except:
                pass
    
    def handle_client(self, sock, pid):
        """Handle client connection"""
        self.clients[pid] = sock
        print(f"{pid} connected")
        
        buf = ""
        while self.running:
            try:
                data = sock.recv(4096).decode()
                if not data:
                    break
                
                buf += data
                while '\n' in buf:
                    line, buf = buf.split('\n', 1)
                    self.handle_input(pid, json.loads(line))
            except:
                break
        
        del self.clients[pid]
        print(f"{pid} disconnected")
    
    def run(self, port):
        """Run server"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', port))
        sock.listen(2)
        print(f"🎮 Snake Battle Server started on port {port}")
        print("⏳ Waiting for players to connect...")
        
        # Accept player 1
        print("   Waiting for Player 1...")
        c1, a1 = sock.accept()
        print(f"   ✓ Player 1 connected from {a1}")
        threading.Thread(target=self.handle_client, args=(c1, 'player1'), daemon=True).start()
        
        # Accept player 2
        print("   Waiting for Player 2...")
        c2, a2 = sock.accept()
        print(f"   ✓ Player 2 connected from {a2}")
        threading.Thread(target=self.handle_client, args=(c2, 'player2'), daemon=True).start()
        
        print("🎮 Both players connected! Game starting...")
        
        # Game loop
        pygame.init()
        clock = pygame.time.Clock()
        
        while self.running and self.clients:
            self.update()
            self.broadcast()
            clock.tick(FPS)
            
            if self.state['over']:
                self.write_result()
                print("🏁 Game ended!")
                time.sleep(3)
                break
        
        sock.close()
        print("👋 Server stopped")
    
    def write_result(self):
        """Write game result to file"""
        try:
            import os
            result = f"Winner: {self.state['winner']} | P1: {self.state['player1']['score']} vs P2: {self.state['player2']['score']}"
            with open(os.path.join(os.path.dirname(__file__), 'game_result.txt'), 'w') as f:
                f.write(result)
            print(f"✅ {result}")
        except Exception as e:
            print(f"⚠️  {e}")


class GameClient:
    """Client - only input and rendering"""
    def __init__(self, pid):
        print(f"🎮 Initializing Snake Battle Client...")
        pygame.init()
        print(f"✓ Pygame initialized")
        
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption(f"Snake Battle - {pid}")
        print(f"✓ Game window created ({WINDOW_WIDTH}x{WINDOW_HEIGHT})")
        
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        
        self.pid = pid
        self.running = True
        self.sock = None
        self.state = None
        self.pending_input = {}
        
        print(f"✓ Client ready!")
    
    def connect(self, host, port):
        """Connect to server"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"🔌 Connecting to {host}:{port}...")
        
        for i in range(10):
            try:
                self.sock.connect((host, port))
                print(f"✓ Connected to server!")
                print(f"⏳ Waiting for other player to join...")
                threading.Thread(target=self.recv_loop, daemon=True).start()
                return True
            except Exception as e:
                if i == 9:
                    print(f"✗ Failed to connect: {e}")
                    return False
                print(f"   Retry {i+1}/10...")
                time.sleep(1)
        return False
    
    def recv_loop(self):
        """Receive state from server"""
        buf = ""
        while self.running:
            try:
                data = self.sock.recv(8192).decode()
                if not data:
                    break
                
                buf += data
                while '\n' in buf:
                    line, buf = buf.split('\n', 1)
                    self.state = json.loads(line)
            except:
                break
    
    def send_input(self, data):
        """Send input to server"""
        try:
            self.sock.sendall((json.dumps(data) + '\n').encode())
        except:
            pass
    
    def handle_events(self):
        """Handle pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            if event.type == pygame.KEYDOWN:
                if not self.state or not self.state['started']:
                    if event.key == pygame.K_SPACE:
                        self.send_input({'start': True})
                else:
                    if event.key == pygame.K_UP:
                        self.pending_input['direction'] = list(UP)
                    elif event.key == pygame.K_DOWN:
                        self.pending_input['direction'] = list(DOWN)
                    elif event.key == pygame.K_LEFT:
                        self.pending_input['direction'] = list(LEFT)
                    elif event.key == pygame.K_RIGHT:
                        self.pending_input['direction'] = list(RIGHT)
                    elif event.key == pygame.K_SPACE:
                        self.pending_input['fire'] = True
    
    def draw(self):
        """Render game state"""
        self.screen.fill(BLACK)
        
        if not self.state:
            # Waiting for connection
            texts = [
                self.font.render("Waiting for other player...", True, WHITE),
                self.small_font.render("Game will start when both players are ready", True, GRAY)
            ]
            for i, t in enumerate(texts):
                self.screen.blit(t, (400 - t.get_width()//2, 350 + i*40))
            pygame.display.flip()
            return
        
        if not self.state['started']:
            texts = [
                self.font.render("Snake Battle", True, WHITE),
                self.small_font.render(f"You are: {self.pid}", True, RED if self.pid == 'player1' else BLUE),
                self.small_font.render("", True, WHITE),
                self.small_font.render("Press SPACE to start the game", True, GREEN),
                self.small_font.render("", True, WHITE),
                self.small_font.render("Controls:", True, YELLOW),
                self.small_font.render("Arrow Keys: Move", True, GRAY),
                self.small_font.render("SPACE: Shoot Fire", True, GRAY)
            ]
            for i, t in enumerate(texts):
                self.screen.blit(t, (400 - t.get_width()//2, 200 + i*40))
            pygame.display.flip()
            return
        
        # Grid
        for x in range(0, 800, CELL_SIZE):
            pygame.draw.line(self.screen, GRAY, (x, 0), (x, 800))
        for y in range(0, 800, CELL_SIZE):
            pygame.draw.line(self.screen, GRAY, (0, y), (800, y))
        
        # Food
        fx, fy = self.state['food']
        pygame.draw.circle(self.screen, GREEN, 
                          (fx*CELL_SIZE + CELL_SIZE//2, fy*CELL_SIZE + CELL_SIZE//2), 
                          CELL_SIZE//2 - 2)
        
        # Snakes
        for pk, color in [('player1', RED), ('player2', BLUE)]:
            p = self.state[pk]
            if p['alive']:
                for i, (x, y) in enumerate(p['snake']):
                    c = color if i == 0 else tuple(c//2 for c in color)
                    pygame.draw.rect(self.screen, c, (x*CELL_SIZE, y*CELL_SIZE, CELL_SIZE, CELL_SIZE))
        
        # Fires
        for pk in ['player1', 'player2']:
            for fire in self.state[pk]['fires']:
                x, y = fire['pos']
                pygame.draw.circle(self.screen, ORANGE, 
                                 (x*CELL_SIZE + CELL_SIZE//2, y*CELL_SIZE + CELL_SIZE//2), 
                                 CELL_SIZE//3)
        
        # HUD
        t1 = self.small_font.render(f"P1: {self.state['player1']['score']}", True, RED)
        t2 = self.small_font.render(f"P2: {self.state['player2']['score']}", True, BLUE)
        self.screen.blit(t1, (10, 10))
        self.screen.blit(t2, (790 - t2.get_width(), 10))
        
        # Fire cooldown
        cd = self.state[self.pid]['fire_cooldown']
        if cd > 0:
            t = self.small_font.render(f"Fire: {cd//10 + 1}s", True, YELLOW)
        else:
            t = self.small_font.render("Fire: READY", True, GREEN)
        self.screen.blit(t, (400 - t.get_width()//2, 10))
        
        # Game over
        if self.state['over']:
            s = pygame.Surface((800, 800))
            s.set_alpha(128)
            s.fill(BLACK)
            self.screen.blit(s, (0, 0))
            
            t = self.font.render(f"Winner: {self.state['winner']}", True, WHITE)
            self.screen.blit(t, (400 - t.get_width()//2, 400))
        
        pygame.display.flip()
    
    def run(self):
        """Main loop"""
        print(f"🎮 Starting game loop...")
        print(f"   Window should be visible now!")
        print(f"   Use Arrow Keys to move, SPACE to fire")
        
        frame_count = 0
        while self.running:
            self.handle_events()
            
            if self.pending_input:
                self.send_input(self.pending_input)
                self.pending_input = {}
            
            self.draw()
            self.clock.tick(FPS)
            
            # Debug: Print status every 5 seconds
            frame_count += 1
            if frame_count % (FPS * 5) == 0:
                if self.state:
                    if self.state['started']:
                        print(f"   Game running... (P1: {self.state['player1']['score']}, P2: {self.state['player2']['score']})")
                    else:
                        print(f"   Waiting for game to start (press SPACE)")
                else:
                    print(f"   Waiting for server state...")
        
        print(f"👋 Client stopped")
        pygame.quit()


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python game.py server [--port PORT]")
        print("  python game.py client --host HOST [--port PORT]")
        sys.exit(1)
    
    mode = sys.argv[1]
    port = 5001
    
    if '--port' in sys.argv:
        port = int(sys.argv[sys.argv.index('--port') + 1])
    
    if mode == 'server':
        GameServer().run(port)
    
    elif mode == 'client':
        host = 'localhost'
        if '--host' in sys.argv:
            host = sys.argv[sys.argv.index('--host') + 1]
        
        print(f"\n{'='*50}")
        print(f"🐍 Snake Battle Client")
        print(f"{'='*50}")
        
        client = GameClient('player1')
        
        if client.connect(host, port):
            print(f"\n🎮 Starting game...")
            print(f"   If you don't see the window, check if it's hidden behind other windows!")
            client.run()
        else:
            print(f"\n✗ Failed to connect to server")
            print(f"   Please make sure the game server is running on {host}:{port}")
            pygame.quit()
    
    else:
        print(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
