# client_gui.py
# CLI (menu-driven) + Pygame GUI client for the Tetris assignment
# - Connects to Lobby Server for register/login/rooms/invites/start
# - After START (or GAME_SERVER_INFO push), connects to Game Server and runs pygame GUI
# - On GAME_OVER, GUI closes and returns to CLI
import pygame, threading, time, sys, socket, argparse
from collections import deque
from utils import send_msg, recv_msg
import select

# ------------------------- GUI constants -------------------------
CELL=22; BORDER=8; BOARD_W=10; BOARD_H=20
SIDE_W=8*CELL; WINDOW_W=BOARD_W*CELL + SIDE_W + BORDER*4; WINDOW_H=BOARD_H*CELL + BORDER*4 + 40
FPS=30
COLORS={'.':(30,34,40),'I':(80,220,240),'O':(240,200,80),'T':(180,100,220),'S':(100,220,120),'Z':(220,80,120),'L':(240,140,60),'J':(80,120,240),'#':(200,200,200)}
BG=(20,20,24); PANEL=(30,32,36); WHITE=(230,230,230); GRID=(80,80,80)

# ------------------------- Lobby connection -------------------------
class LobbyConn:
    """
    A single TCP connection to the Lobby Server.
    - send_request: sends a message and waits for a matching *_RESP (or expected type)
    - recv thread: handles push messages (INVITED, GAME_SERVER_INFO, MATCH_ENDED) and enqueues responses
    """
    def __init__(self, host, port):
        self.host=host; self.port=port
        self.sock=None
        self.rx_thread=None
        self.running=False
        self.user=None  # {'id','name'} after login
        self._resp_q=deque()
        self._cv=threading.Condition()
        self._push_handlers=[]
        self._heartbeat_thread=None

    # ---- socket helpers
    def connect(self):
        self.sock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host,self.port))
        self.running=True
        self.rx_thread=threading.Thread(target=self._recv_loop, daemon=True)
        self.rx_thread.start()

    def close(self):
        self.running=False
        try:
            if self.sock: self.sock.close()
        except: pass
        self.sock=None

    # ---- push registration
    def on_push(self, func):
        """ func(msg_dict) -> None """
        self._push_handlers.append(func)

    # ---- request/response
    def send_request(self, msg, expected_types=None, timeout=5.0):
        """
        Send a request and wait for a response message whose 'type' is in expected_types.
        If expected_types is None, infer "*_RESP" from msg['type'].
        """
        if expected_types is None:
            t=msg.get('type','') + '_RESP'
            expected_types=[t]
        try:
            send_msg(self.sock, msg)
        except Exception as e:
            raise ConnectionError(f"send failed: {e}")
        # wait
        end=time.time()+timeout
        with self._cv:
            while True:
                # try to pop matching resp
                for i,m in enumerate(self._resp_q):
                    if m.get('type') in expected_types:
                        self._resp_q.remove(m)
                        return m
                # timeout?
                now=time.time()
                if now>=end:
                    raise TimeoutError(f"waiting response {expected_types} timed out")
                # wait for new msg
                self._cv.wait(timeout=end-now)

    # ---- background recv
    def _recv_loop(self):
        while self.running:
            try:
                msg=recv_msg(self.sock)
                if not msg:
                    break
                t=msg.get('type','')
                # detect pushes
                if t in ('INVITED','GAME_SERVER_INFO','MATCH_ENDED','MEMBER_JOINED','ROOM_DROPPED'):
                    for fn in self._push_handlers:
                        try: fn(msg)
                        except: pass
                else:
                    with self._cv:
                        self._resp_q.append(msg)
                        self._cv.notify_all()
            except Exception:
                break
        self.running=False

    # ---- heartbeat
    def start_heartbeat(self, user_id, period=5):
        def hb():
            while self.running and self.user and self.user.get('id')==user_id:
                try:
                    send_msg(self.sock, {'type':'HEARTBEAT','data':{}})
                except Exception:
                    break
                time.sleep(period)
        self._heartbeat_thread=threading.Thread(target=hb, daemon=True)
        self._heartbeat_thread.start()

# ------------------------- Pygame Game client -------------------------
class GameClient:
    """
    Pygame GUI that connects directly to Game Server.
    IMPORTANT: server uses internal player ids 0/1, so we map 'me' by role from WELCOME:
      P1 -> my_pid=0 ; P2 -> my_pid=1
    Spectator mode: role='SPECTATOR', can view both players but cannot send input
    """
    def __init__(self, host, port, spectator=False, user_name=None):
        self.host=host; self.port=port
        self.sock=None; self.connected=False; self.running=True
        self.role='?'; self.my_pid=None
        self.is_spectator=spectator
        self.user_name=user_name
        self.lock=threading.Lock()
        # Store player names for display (pid -> name)
        self.player_names = {}
        # Ensure pygame is properly initialized (safe to call multiple times)
        if not pygame.get_init():
            pygame.init()
        pygame.display.set_caption("Tetris Client")
        self.screen=pygame.display.set_mode((WINDOW_W,WINDOW_H)); self.clock=pygame.time.Clock()
        self.state={'mode':'timed','durationSec':60,
                    'me':{'board':[['.' for _ in range(BOARD_W)] for __ in range(BOARD_H)],'score':0,'lines':0,'active':None,'next':[]},
                    'opp':{'board':[['.' for _ in range(BOARD_W)] for __ in range(BOARD_H)],'score':0,'lines':0,'active':None},
                    'tick':0}
        self.start_ts=None
        # store snapshots received before WELCOME; applied after role known
        self._pending_snaps = {}
        # For smooth falling animation: keep a continuous render_y that eases
        # toward the latest target y received from snapshots. This avoids
        # jumps when snapshots arrive out-of-order or when WELCOME comes late.
        self._active_anim = {
            'me': {'render_x': None, 'render_y': None, 'target_x': None, 'target_y': None, 'last_ts': None},
            'opp': {'render_x': None, 'render_y': None, 'target_x': None, 'target_y': None, 'last_ts': None}
        }

        # piece templates (copied from server) for rendering active piece
        self.TET = {
         'I':[[(0,1),(1,1),(2,1),(3,1)],[(2,0),(2,1),(2,2),(2,3)],[(0,2),(1,2),(2,2),(3,2)],[(1,0),(1,1),(1,2),(1,3)]],
         'O':[[(1,0),(2,0),(1,1),(2,1)]]*4,
         'T':[[(1,0),(0,1),(1,1),(2,1)],[(1,0),(1,1),(2,1),(1,2)],[(0,1),(1,1),(2,1),(1,2)],[(1,0),(0,1),(1,1),(1,2)]],
         'J':[[(0,0),(0,1),(1,1),(2,1)],[(1,0),(2,0),(1,1),(1,2)],[(0,1),(1,1),(2,1),(2,2)],[(1,0),(1,1),(0,2),(1,2)]],
         'L':[[(2,0),(0,1),(1,1),(2,1)],[(1,0),(1,1),(1,2),(2,2)],[(0,1),(1,1),(2,1),(0,2)],[(0,0),(1,0),(1,1),(1,2)]],
         'S':[[(1,0),(2,0),(0,1),(1,1)],[(1,0),(1,1),(2,1),(2,2)],[(1,1),(2,1),(0,2),(1,2)],[(0,0),(0,1),(1,1),(1,2)]],
         'Z':[[(0,0),(1,0),(1,1),(2,1)],[(2,0),(1,1),(2,1),(1,2)],[(0,1),(1,1),(1,2),(2,2)],[(1,0),(0,1),(1,1),(0,2)]],
        }
        print("Controls: ←/→ move, ↑ rotate, ↓ soft drop, Space hard drop, Esc quit")

    def connect(self, user_id):
        self.user_id=user_id
        self.sock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Set socket timeout to prevent recv_msg from blocking forever
        self.sock.settimeout(5.0)
        self.sock.connect((self.host,self.port))
        hello_msg = {'type':'HELLO','version':1,'roomId':0,'userId':user_id,'roomToken':''}
        if self.user_name:
            hello_msg['userName'] = self.user_name
        if self.is_spectator:
            hello_msg['spectator'] = True
        send_msg(self.sock, hello_msg)
        self.connected=True
        threading.Thread(target=self._recv_loop, daemon=True).start()
        role_str = "spectator" if self.is_spectator else f"player uid={user_id}"
        print(f"[GUI] Connected to game server {self.host}:{self.port} as {role_str}")

    def _recv_loop(self):
        try:
            while self.running:
                try:
                    msg=recv_msg(self.sock)
                    if not msg: break
                except socket.timeout:
                    # Timeout is normal, just continue checking self.running
                    continue
                except Exception as e:
                    if self.running:
                        print(f"[GUI] recv error: {e}")
                    break
                t=msg.get('type')
                if t=='WELCOME':
                    # log welcome payload for debugging mode/role propagation
                    print(f"[GUI] Received WELCOME: role={msg.get('role')} mode={msg.get('mode')} dur={msg.get('durationSec')}")
                    with self.lock:
                        self.role=msg.get('role','?')
                        self.my_pid = 0 if self.role=='P1' else 1 if self.role=='P2' else None
                        self.state['mode']=msg.get('mode','timed')
                        self.state['durationSec']=int(msg.get('durationSec',60))
                        self.start_ts=time.time()
                        # Store player names
                        players_info = msg.get('players', {})
                        for pid_str, info in players_info.items():
                            try:
                                pid = int(pid_str)
                                self.player_names[pid] = info.get('userName', f'Player{pid+1}')
                            except:
                                pass
                        # apply any snapshots we buffered while waiting for WELCOME
                        if self._pending_snaps:
                            for pid, snap in list(self._pending_snaps.items()):
                                try:
                                    self._apply_snapshot(snap)
                                except Exception:
                                    pass
                            self._pending_snaps.clear()
                elif t=='PLAYER_UPDATE':
                    # Update player names when a new player joins
                    with self.lock:
                        players_info = msg.get('players', {})
                        for pid_str, info in players_info.items():
                            try:
                                pid = int(pid_str)
                                self.player_names[pid] = info.get('userName', f'Player{pid+1}')
                            except:
                                pass
                elif t=='SNAPSHOT':
                    self._apply_snapshot(msg)
                elif t=='GAME_OVER':
                    print("[GUI] GAME OVER:", msg.get('data',{}))
                    # mark stop and post a QUIT event so the main thread's event loop
                    # will immediately handle window close (important on some platforms)
                    self.running=False
                    try:
                        pygame.event.post(pygame.event.Event(pygame.QUIT))
                    except Exception:
                        pass
                else:
                    pass
        except Exception as e:
            print("[GUI] recv end:", e)
        finally:
            self.connected=False

    def _apply_snapshot(self, snap):
        pid=snap.get('userId')
        with self.lock:
            # For spectators, map pid directly: 0->me(P1), 1->opp(P2)
            if self.is_spectator:
                # Spectator mode: treat pid 0 as Player 1 (left/me), pid 1 as Player 2 (right/opp)
                dst = self.state['me'] if pid == 0 else self.state['opp']
                side = 'me' if pid == 0 else 'opp'
            else:
                # if we don't yet know our role/my_pid (WELCOME not arrived),
                # buffer the snapshot so we don't incorrectly infer my_pid from first snap
                if self.my_pid is None:
                    try:
                        self._pending_snaps[pid] = snap
                    except Exception:
                        pass
                    return
                is_me = (pid == self.my_pid)
                dst = self.state['me'] if is_me else self.state['opp']
                side = 'me' if is_me else 'opp'
            
            dst['board']=snap['board']
            dst['lines']=snap['lines']
            dst['score']=snap['score']
            # animate active piece: store previous y and target y with timestamp
            active = snap.get('active')
            prev = dst.get('active')
            dst['active']=active
            try:
                # update the continuous animation target and ensure render_y
                # is initialized if missing. We use a simple easing during
                # render to move render_y toward target.
                anim = self._active_anim[side]
                if active:
                    try:
                        anim['target_y'] = float(active.get('y'))
                    except Exception:
                        anim['target_y'] = None
                    try:
                        anim['target_x'] = float(active.get('x'))
                    except Exception:
                        anim['target_x'] = None
                else:
                    anim['target_y'] = None
                    anim['target_x'] = None
                nowt = time.time()
                anim['last_ts'] = nowt
                # initialize render positions if missing
                if anim.get('render_y') is None and anim.get('target_y') is not None:
                    anim['render_y'] = anim['target_y']
                if anim.get('render_x') is None and anim.get('target_x') is not None:
                    anim['render_x'] = anim['target_x']
            except Exception:
                pass
            # Update 'next' pieces only for the player's own view (or P1 in spectator mode)
            if self.is_spectator:
                # For spectators, only update 'next' for Player 1 (pid 0)
                if pid == 0 and 'next' in snap:
                    dst['next']=snap['next']
            else:
                # For players, only update 'next' for own board
                is_me = (pid == self.my_pid)
                if is_me and 'next' in snap:
                    dst['next']=snap['next']
            self.state['mode']=snap.get('mode',self.state['mode'])
            self.state['durationSec']=snap.get('durationSec',self.state['durationSec'])
            self.state['tick']=snap['tick']

    def _draw_active_piece(self, surf, active, x0, y0, cell, x_offset_pixels=0, y_offset_pixels=0):
        if not active: return
        shape = active.get('shape')
        rot = int(active.get('rot',0))
        x = int(active.get('x',0))
        y = int(active.get('y',0))
        # draw each cell of the piece with an extra pixel offset
        coords = self.TET.get(shape, [])
        if not coords: return
        for (cx,cy) in coords[rot % len(coords)]:
            px = x0 + (x + cx) * cell + int(x_offset_pixels)
            py = y0 + (y + cy) * cell + int(y_offset_pixels)
            pygame.draw.rect(surf, COLORS.get(shape, COLORS['#']), (px, py, cell-1, cell-1))

    def _send_input(self, act):
        if not self.connected: return
        try:
            send_msg(self.sock, {'type':'INPUT','userId':self.user_id,'seq':int(time.time()*1000),'ts':int(time.time()*1000),'action':act})
        except Exception:
            self.connected=False

    def _draw_board(self, surf, board, x0, y0, cell):
        for r in range(BOARD_H):
            for c in range(BOARD_W):
                ch=board[r][c] if isinstance(board[r][c],str) else '#'
                pygame.draw.rect(surf, COLORS.get(ch, COLORS['#']), (x0+c*cell, y0+r*cell, cell-1, cell-1))
        pygame.draw.rect(surf, GRID, (x0-1,y0-1,BOARD_W*cell+2,BOARD_H*cell+2),1)
    
    def _render_spectator(self):
        """Render both players side by side for spectator view"""
        with self.lock:
            me=self.state['me']; opp=self.state['opp']
            mode=self.state['mode']; dur=self.state['durationSec']
        
        # Calculate layout - two boards side by side
        cell = int(CELL * 0.8)  # slightly smaller cells to fit both boards
        gap = BORDER * 4
        board1_x = BORDER * 2
        board2_x = board1_x + BOARD_W * cell + gap
        board_y = BORDER + 40
        
        # Get player names
        p1_name = self.player_names.get(0, 'Player 1')
        p2_name = self.player_names.get(1, 'Player 2')
        
        # Draw Player 1 (left side)
        pygame.draw.rect(self.screen, PANEL, (board1_x-4, board_y-4, BOARD_W*cell+8, BOARD_H*cell+8))
        self._draw_board(self.screen, me['board'], board1_x, board_y, cell)
        # Draw active piece for Player 1
        if me.get('active'):
            self._draw_active_piece(self.screen, me['active'], board1_x, board_y, cell)
        # Player 1 info
        font = pygame.font.SysFont('Consolas', 14)
        p1_label = font.render(f"{p1_name} - Score: {me['score']} Lines: {me['lines']}", True, WHITE)
        self.screen.blit(p1_label, (board1_x, board_y - 25))
        
        # Draw Player 2 (right side)
        pygame.draw.rect(self.screen, PANEL, (board2_x-4, board_y-4, BOARD_W*cell+8, BOARD_H*cell+8))
        self._draw_board(self.screen, opp['board'], board2_x, board_y, cell)
        # Draw active piece for Player 2
        if opp.get('active'):
            self._draw_active_piece(self.screen, opp['active'], board2_x, board_y, cell)
        # Player 2 info
        p2_label = font.render(f"{p2_name} - Score: {opp['score']} Lines: {opp['lines']}", True, WHITE)
        self.screen.blit(p2_label, (board2_x, board_y - 25))
        
        # Top bar with game info
        tl = '--'
        if mode == 'timed' and self.start_ts:
            elapsed = int(time.time() - self.start_ts)
            remain = max(0, dur - elapsed)
            tl = f"{remain // 60}:{remain % 60:02d}"
        title_font = pygame.font.SysFont('Consolas', 16)
        top = title_font.render(f"SPECTATOR MODE - {mode} - Time: {tl}", True, WHITE)
        self.screen.blit(top, (BORDER, 4))
        
        # Bottom control hint
        ctrl = pygame.font.SysFont('Consolas', 14).render("Esc: Quit (Spectator - No Controls)", True, WHITE)
        self.screen.blit(ctrl, (BORDER, WINDOW_H - 28))
        
        pygame.display.flip()

    def _render(self):
        self.screen.fill(BG)
        # For spectator mode, show both players side by side with equal size
        if self.is_spectator:
            self._render_spectator()
            return
        board_x=BORDER; board_y=BORDER+20; right_x=board_x+BOARD_W*CELL+BORDER*2
        with self.lock:
            me=self.state['me']; opp=self.state['opp']; role=self.role
            mode=self.state['mode']; dur=self.state['durationSec']
            # compute animation offsets for active pieces
            now = time.time()
            me_offset = 0
            try:
                anim = self._active_anim['me']
                # perform easing toward target_x/target_y based on frame dt
                if anim.get('render_y') is not None and anim.get('target_y') is not None:
                    last = anim.get('last_ts') or now
                    dt = max(0.0, now - last)
                    # smoothing speed (rows per second); tweakable - increased for smoother fall
                    speed = 20.0  # increased from 14.0
                    factor = 1.0 - pow(0.001, dt * speed)  # quick ease curve, in (0,1]
                    diff_y = anim['target_y'] - anim['render_y']
                    # if the difference is large, snap to avoid long glide
                    if abs(diff_y) > 3.0:  # reduced threshold from 4.0 for quicker catch-up
                        anim['render_y'] = anim['target_y']
                    else:
                        anim['render_y'] += diff_y * factor
                    # offset = render_y - target_y (pixels)
                    me_offset = (anim['render_y'] - anim['target_y']) * CELL
                # horizontal smoothing
                x_offset_pix = 0
                if anim.get('render_x') is not None and anim.get('target_x') is not None:
                    last = anim.get('last_ts') or now
                    dt = max(0.0, now - last)
                    speed_x = 25.0  # increased from 20.0 for faster horizontal movement
                    factor_x = 1.0 - pow(0.001, dt * speed_x)
                    diff_x = anim['target_x'] - anim['render_x']
                    if abs(diff_x) > 3.0:  # reduced threshold from 4.0
                        anim['render_x'] = anim['target_x']
                    else:
                        anim['render_x'] += diff_x * factor_x
                    x_offset_pix = (anim['render_x'] - anim['target_x']) * CELL
                # update last_ts
                anim['last_ts'] = now
                # ensure variables exist for downstream
                try:
                    me_offset
                except NameError:
                    me_offset = 0
                try:
                    x_offset_pix
                except NameError:
                    x_offset_pix = 0
            except Exception:
                me_offset = 0
        pygame.draw.rect(self.screen, PANEL, (board_x-4,board_y-4,BOARD_W*CELL+8,BOARD_H*CELL+8))
        self._draw_board(self.screen, me['board'], board_x, board_y, CELL)
        # draw active piece on top for smooth falling animation (me)
        try:
            self._draw_active_piece(self.screen, me.get('active'), board_x, board_y, CELL, x_offset_pixels=x_offset_pix, y_offset_pixels=me_offset)
        except Exception:
            pass
        pygame.draw.rect(self.screen, PANEL, (right_x-4,board_y-4,SIDE_W,BOARD_H*CELL+8))
        small=int(CELL*0.6); sx=right_x + (SIDE_W - BOARD_W*small)//2
        self._draw_board(self.screen, opp['board'], sx, board_y, small)
        # draw opponent's active piece with smooth animation
        opp_offset = 0
        opp_x_offset = 0
        try:
            anim_opp = self._active_anim['opp']
            if anim_opp.get('render_y') is not None and anim_opp.get('target_y') is not None:
                last = anim_opp.get('last_ts') or now
                dt = max(0.0, now - last)
                speed = 20.0  # increased from 14.0 for smoother fall
                factor = 1.0 - pow(0.001, dt * speed)
                diff_y = anim_opp['target_y'] - anim_opp['render_y']
                if abs(diff_y) > 3.0:  # reduced threshold from 4.0
                    anim_opp['render_y'] = anim_opp['target_y']
                else:
                    anim_opp['render_y'] += diff_y * factor
                opp_offset = (anim_opp['render_y'] - anim_opp['target_y']) * small
            # horizontal smoothing for opponent
            if anim_opp.get('render_x') is not None and anim_opp.get('target_x') is not None:
                last = anim_opp.get('last_ts') or now
                dt = max(0.0, now - last)
                speed_x = 25.0  # increased from 20.0 for faster horizontal movement
                factor_x = 1.0 - pow(0.001, dt * speed_x)
                diff_x = anim_opp['target_x'] - anim_opp['render_x']
                if abs(diff_x) > 3.0:  # reduced threshold from 4.0
                    anim_opp['render_x'] = anim_opp['target_x']
                else:
                    anim_opp['render_x'] += diff_x * factor_x
                opp_x_offset = (anim_opp['render_x'] - anim_opp['target_x']) * small
            anim_opp['last_ts'] = now
        except Exception:
            opp_offset = 0
            opp_x_offset = 0
        # draw opponent's active piece on top with animation
        try:
            self._draw_active_piece(self.screen, opp.get('active'), sx, board_y, small, x_offset_pixels=opp_x_offset, y_offset_pixels=opp_offset)
        except Exception:
            pass
        # Get player names for display
        my_name = self.player_names.get(self.my_pid, 'Me') if self.my_pid is not None else 'Me'
        opp_pid = 1 - self.my_pid if self.my_pid is not None else None
        opp_name = self.player_names.get(opp_pid, 'Opponent') if opp_pid is not None else 'Opponent'
        
        font=pygame.font.SysFont('Consolas',16)
        tl='--'
        if mode=='timed' and self.start_ts:
            left=max(0,int(dur - (time.time()-self.start_ts)))
            tl=str(left)+'s'
        top=font.render(f"{my_name} vs {opp_name}   mode={mode}   time={tl}   me:{me['lines']}L   opp:{opp['lines']}L", True, WHITE)
        self.screen.blit(top,(BORDER,4))
        ctrl=pygame.font.SysFont('Consolas',14).render("<- ->:Move  Up:Rotate  Down:Soft  Space:Hard  Esc:Quit", True, WHITE)
        self.screen.blit(ctrl,(BORDER,WINDOW_H-28))
        pygame.display.flip()

    def run(self, user_id):
        self.connect(user_id)
        try:
            while self.running:
                try:
                    for e in pygame.event.get():
                        if e.type==pygame.QUIT: self.running=False
                        if e.type==pygame.KEYDOWN:
                            if e.key==pygame.K_ESCAPE: self.running=False
                            # Only send input if not spectator
                            if not self.is_spectator:
                                if e.key==pygame.K_LEFT: self._send_input('LEFT')
                                if e.key==pygame.K_RIGHT: self._send_input('RIGHT')
                                if e.key==pygame.K_UP: self._send_input('ROT')
                                if e.key==pygame.K_DOWN: self._send_input('SOFT')
                                if e.key==pygame.K_SPACE: self._send_input('DROP')
                    self._render(); self.clock.tick(FPS)
                except Exception as e:
                    print(f"[GUI] Error in main loop: {e}")
                    break
        finally:
            print("[GUI] Cleaning up...")
            # Mark as not running to stop recv_loop
            self.running = False
            # Close socket first to interrupt recv_loop thread
            try: 
                if self.sock:
                    self.sock.shutdown(socket.SHUT_RDWR)
            except: 
                pass
            try:
                if self.sock:
                    self.sock.close()
            except: 
                pass
            # Wait a moment for recv_loop to finish
            time.sleep(0.2)
            # Then quit pygame - but don't call quit() to allow re-init
            # Just close the display window
            try:
                pygame.display.quit()
            except Exception as e:
                print(f"[GUI] Error closing display: {e}")
            print("[GUI] Cleanup complete")
        return  # back to CLI

# ------------------------- CLI (menu-driven) -------------------------
class ClientApp:
    def __init__(self, lobby_host='127.0.0.1', lobby_port=13000):
        self.lobby = LobbyConn(lobby_host, lobby_port)
        self.lobby.connect()
        self.lobby.on_push(self._on_push)
        self.logged_in=False
        self.user=None              # {'id','name'}
        self.last_created_room_id=None
        self._invite_cache=[]       # from POLL_INVITES
        self._push_game_info=None   # store latest GAME_SERVER_INFO
        self._in_game = False
        self._game_done_event = threading.Event()
        self._pending_game_info = False
        # prevent immediate re-launch of GUI for the same game port after it ended
        self._last_game_port = None
        self._last_game_end_ts = 0.0

        # auto poll invites every 5s
        self._poll_running=True
        threading.Thread(target=self._auto_poll_invites, daemon=True).start()

    # -------- background helpers --------
    def _auto_poll_invites(self):
        while self._poll_running:
            try:
                if self.logged_in:
                    resp=self.lobby.send_request({'type':'POLL_INVITES','data':{}}, expected_types=['POLL_INVITES_RESP'], timeout=3)
                    if resp.get('data',{}).get('ok'):
                        invites=resp['data']['invites']
                        # print any new invites
                        for inv in invites:
                            mark=(inv['roomId'],inv['fromUserId'])
                            if mark not in [(i['roomId'],i['fromUserId']) for i in self._invite_cache]:
                                print(f"\n[Push] You are invited to room #{inv['roomId']} \"{inv['roomName']}\" by user {inv['fromUserId']} (mode: {inv['mode']}, dur:{inv['durationSec']}s)")
                        self._invite_cache=invites
            except Exception:
                pass
            time.sleep(5)

    def _on_push(self, msg):
        t=msg.get('type')
        if t=='INVITED':
            d=msg.get('data',{})
            rid = d.get('roomId')
            rname = d.get('roomName')
            frm = d.get('fromUserId')
            frm_name = d.get('fromUserName', f"User#{frm}")
            mode = d.get('mode')
            dur = d.get('durationSec')
            print(f"\n[Push] INVITED to room #{rid} \"{rname}\" (mode: {mode}, dur:{dur}s) from {frm_name}")
            # cache invite for menu/polling; do NOT prompt immediately (user must choose menu option 6 to accept)
            try:
                self._invite_cache.append({'roomId': rid, 'fromUserId': frm, 'fromUserName': frm_name, 'roomName': rname, 'mode': mode, 'durationSec': dur})
            except Exception:
                self._invite_cache = [{'roomId': rid, 'fromUserId': frm, 'fromUserName': frm_name, 'roomName': rname, 'mode': mode, 'durationSec': dur}]
        elif t=='GAME_SERVER_INFO':
            d=msg.get('data',{})
            print(f"\n[Push] GAME SERVER: {d.get('host')}:{d.get('port')}  mode={d.get('mode')}  dur={d.get('durationSec')}s")
            # Debounce: if we just finished a game on this port, ignore quick re-push
            try:
                port = int(d.get('port'))
            except Exception:
                port = None
            now = time.time()
            if port is not None and self._last_game_port == port and (now - self._last_game_end_ts) < 2.0:
                # ignore this stale push
                print(f"[Push] Ignored GAME_SERVER_INFO for recently finished port {port}")
                return
            # Also ignore if we're currently in a game (prevents double-launch)
            if self._in_game:
                print(f"[Push] Ignored GAME_SERVER_INFO because already in game")
                return
            self._push_game_info=d
            # Mark pending game info so main thread can launch GUI (pygame must be init'd on main thread)
            self._pending_game_info = True
        elif t=='MATCH_ENDED':
            d=msg.get('data',{})
            print(f"\n[Push] MATCH ENDED for room #{d.get('roomId')}. Results: {d.get('results')}")
        elif t=='MEMBER_JOINED':
            d=msg.get('data',{})
            rid = d.get('roomId')
            rname = d.get('roomName', f'Room#{rid}')
            uname = d.get('userName', f"User#{d.get('userId')}")
            count = d.get('memberCount', 0)
            print(f"\n[Push] {uname} joined your room #{rid} \"{rname}\" (now {count}/2 players)")
        elif t=='ROOM_DROPPED':
            d=msg.get('data',{})
            rid = d.get('roomId')
            rname = d.get('roomName', f'Room#{rid}')
            reason = d.get('reason', 'unknown reason')
            print(f"\n[Push] ⚠️  Room #{rid} \"{rname}\": {reason}")
        else:
            print(f"\n[Push] {t}: {msg}")

    # -------- menus --------
    def run(self):
        try:
            while True:
                if not self.logged_in:
                    if not self.menu_auth(): break
                else:
                    # If push provided game info, launch GUI on main thread (required on macOS/SDL)
                    if self._pending_game_info and self.user and not self._in_game:
                        d = self._push_game_info or {}
                        host = d.get('host')
                        port = d.get('port')
                        if host and port:
                            try:
                                p_int = int(port)
                            except Exception:
                                p_int = None
                            # debounce: if this port was just finished, skip launching
                            if p_int is not None and self._last_game_port == p_int and (time.time() - self._last_game_end_ts) < 2.0:
                                print(f"Skipping auto-launch for recently finished port {p_int}")
                                self._pending_game_info = False
                                self._push_game_info = None
                            else:
                                self._pending_game_info = False
                                user_id = self.user['id']
                                user_name = self.user.get('name', f'User{user_id}')
                                # If game server host is localhost, use lobby's host instead (for remote connections)
                                if host in ('127.0.0.1', 'localhost'):
                                    host = self.lobby.host
                                try:
                                    self._in_game = True
                                    self._last_game_port = p_int
                                    gui = GameClient(host, int(port), user_name=user_name)
                                    gui.run(user_id)
                                except Exception as e:
                                    print("[GUI] Failed to start GUI:", e)
                                finally:
                                    self._in_game = False
                                    self._game_done_event.set()
                                    # mark end time to debounce
                                    self._last_game_end_ts = time.time()
                                    # clear any stale push info
                                    self._push_game_info = None
                    if not self.menu_main(): break
        finally:
            self._poll_running=False
            self.lobby.close()

    def menu_auth(self):
        print("\n==== TETRIS LOBBY ====")
        print("[1] Register")
        print("[2] Login")
        print("[3] Exit")
        choice=input("Select> ").strip()
        if choice=='1':
            name=input("Name: ").strip()
            pw=input("Password: ").strip()
            pw2=input("Confirm password: ").strip()
            if pw!=pw2:
                print("Password not match, please try again.")
                return True
            try:
                resp=self.lobby.send_request({'type':'REGISTER','data':{'name':name,'password':pw}})
                print("REGISTER_RESP:", resp.get('data'))
            except Exception as e:
                print("Register failed:", e)
        elif choice=='2':
            name=input("Name: ").strip()
            pw=input("Password: ").strip()
            try:
                # 🔧 FIX: use Lobby for login, start heartbeat on success
                resp=self.lobby.send_request({'type':'LOGIN','data':{'name':name,'password':pw}})
                data=resp.get('data',{})
                if data.get('ok'):
                    self.logged_in=True
                    self.user=data['user']    # {'id','name'}
                    self.lobby.user=self.user
                    self.lobby.start_heartbeat(self.user['id'])
                    print(f"Logged in as: {self.user['name']} (UserID={self.user['id']})")
                    print(f"Connected to Lobby: {self.lobby.host}:{self.lobby.port}")
                else:
                    print("Login failed:", data.get('error','Unknown error'))
            except Exception as e:
                print("Login failed:", e)
        elif choice=='3':
            return False
        return True

    def menu_main(self):
        print("\n==== MAIN MENU ====")
        print("[1] Show Online Users")
        print("[2] Show Public Rooms")
        print("[3] Create Room")
        print("[4] Invite User")
        print("[5] Check Invitations")
        print("[6] Accept Invitation")
        print("[7] Start Game (host only)")
        print("[8] Join as Spectator")
        print("[9] Logout")
        # Use interruptible prompt so GAME_SERVER_INFO push can trigger GUI immediately
        def _prompt_with_interrupt(prompt, interval=0.5):
            sys.stdout.write(prompt)
            sys.stdout.flush()
            while True:
                # if a game push arrived, return None to signal immediate handling
                if self._pending_game_info and self.user and not self._in_game:
                    return None
                r,_,_ = select.select([sys.stdin], [], [], interval)
                if r:
                    line = sys.stdin.readline()
                    if not line:
                        return ''
                    return line.strip()

        choice = _prompt_with_interrupt("Select> ")
        if choice is None:
            # pending game info: launch GUI on main thread
            d = self._push_game_info or {}
            host = d.get('host'); port = d.get('port')
            if host and port:
                try:
                    p_int = int(port)
                except Exception:
                    p_int = None
                if p_int is not None and self._last_game_port == p_int and (time.time() - self._last_game_end_ts) < 2.0:
                    print(f"Skipping auto-launch for recently finished port {p_int}")
                    self._pending_game_info = False
                    self._push_game_info = None
                    return True
                # Set _in_game BEFORE clearing pending to prevent race condition
                self._in_game = True
                # clear pending and start GUI
                self._pending_game_info = False
                self._push_game_info = None
                self._last_game_port = p_int
                user_id = self.user['id']
                user_name = self.user.get('name', f'User{user_id}')
                try:
                    gui = GameClient(host, int(port), user_name=user_name)
                    gui.run(user_id)
                except Exception as e:
                    print("[GUI] Failed to start GUI:", e)
                finally:
                    self._in_game = False
                    self._game_done_event.set()
                    self._last_game_end_ts = time.time()
                    self._push_game_info = None
            return True
        if choice=='1':
            self.do_list_online()
        elif choice=='2':
            self.do_list_rooms()
        elif choice=='3':
            self.do_create_room()
        elif choice=='4':
            self.do_invite_user()
        elif choice=='5':
            self.do_poll_invites()
        elif choice=='6':
            self.do_accept()
        elif choice=='7':
            self.do_start_game_and_play()
        elif choice=='8':
            self.do_join_spectator()
        elif choice=='9':
            # Send logout request to mark user as offline in DB
            if self.user:
                try:
                    self.lobby.send_request({'type':'LOGOUT','data':{'id':self.user['id']}}, expected_types=['LOGOUT_RESP'], timeout=2.0)
                except Exception:
                    pass
            self.logged_in=False
            self.user=None
            print("Logged out.")
        else:
            print("Unknown selection.")
        return True

    # -------- actions --------
    def do_list_online(self):
        try:
            resp=self.lobby.send_request({'type':'LIST_ONLINE','data':{}}, expected_types=['LIST_ONLINE_RESP'])
            data=resp.get('data',{})
            if data.get('ok'):
                arr=data['result']
                print("Online users:")
                for u in arr:
                    total_score = u.get('totalScore', 0)
                    print(f"  - id={u['id']}  name={u['name']}  totalScore={total_score}")
            else:
                print("Failed:", data)
        except Exception as e:
            print("Error:", e)

    def do_list_rooms(self):
        try:
            resp=self.lobby.send_request({'type':'LIST_ROOMS','data':{}}, expected_types=['LIST_ROOMS_RESP'])
            data=resp.get('data',{})
            if data.get('ok'):
                rooms=data['result']
                print("Public rooms:")
                for r in rooms:
                    members=r.get('memberList',[])
                    print(f"  - id=#{r['id']} name=\"{r['name']}\" host={r['hostUserId']} status={r['status']} mode={r['mode']} dur={r['durationSec']}s members={members}")
            else:
                print("Failed:", data)
        except Exception as e:
            print("Error:", e)

    def do_create_room(self):
        name=input("Room name: ").strip() or "room"
        print("Choose mode:\n  [1] Timed (60s)\n  [2] Survival")
        msel=input("Select> ").strip()
        mode='timed' if msel=='1' else 'survival'
        dur=60 if mode=='timed' else 0
        try:
            resp=self.lobby.send_request({'type':'CREATE_ROOM','data':{
                'name':name,'visibility':'public','inviteList':[],
                'mode':mode,'durationSec':dur
            }})
            data=resp.get('data',{})
            if data.get('ok'):
                rid=data['result']['id']
                self.last_created_room_id=rid
                print(f"Room created: id=#{rid}  mode={mode} dur={dur}s")
            else:
                print("Create failed:", data)
        except Exception as e:
            print("Error:", e)

    def do_invite_user(self):
        if not self.last_created_room_id:
            rid=input("Room id to invite into: ").strip()
        else:
            use_last=input(f"Use last created room #{self.last_created_room_id}? [Y/n] ").strip().lower()
            if use_last in ('','y','yes'):
                rid=str(self.last_created_room_id)
            else:
                rid=input("Room id: ").strip()
        tgt=input("Target user id to invite: ").strip()
        try:
            resp=self.lobby.send_request({'type':'INVITE','data':{'roomId':int(rid),'targetUserId':int(tgt)}}, expected_types=['INVITE_RESP'])
            print("INVITE_RESP:", resp.get('data'))
        except Exception as e:
            print("Error:", e)

    def do_poll_invites(self):
        try:
            resp=self.lobby.send_request({'type':'POLL_INVITES','data':{}}, expected_types=['POLL_INVITES_RESP'])
            data=resp.get('data',{})
            if data.get('ok'):
                inv=data['invites']; self._invite_cache=inv
                if not inv:
                    print("No invites.")
                else:
                    print("Invites:")
                    for i in inv:
                        frm_display = i.get('fromUserName', f"User#{i['fromUserId']}")
                        print(f"  - room #{i['roomId']} \"{i['roomName']}\" from {frm_display} (mode: {i['mode']}, dur:{i['durationSec']}s)")
            else:
                print("Failed:", data)
        except Exception as e:
            print("Error:", e)

    def do_accept(self):
        # Refresh invite list first to get latest state (filters out closed rooms)
        try:
            resp = self.lobby.send_request({'type':'POLL_INVITES','data':{}}, expected_types=['POLL_INVITES_RESP'])
            data = resp.get('data',{})
            if data.get('ok'):
                self._invite_cache = data['invites']
        except Exception:
            pass  # continue with cached data if refresh fails
        
        # 如果有推播邀請快取，列出所有邀請並讓使用者選擇要接受哪一個
        if self._invite_cache:
            print("Invites:")
            for i, inv in enumerate(self._invite_cache):
                frm_display = inv.get('fromUserName', f"User#{inv.get('fromUserId')}")
                print(f"  [{i}] room #{inv['roomId']} \"{inv.get('roomName','')}\" from {frm_display} (mode: {inv.get('mode')}, dur:{inv.get('durationSec')}s)")
            sel = input("Select invite index to accept (or Enter to cancel): ").strip()
            if sel == '':
                print("Cancelled.")
                return
            try:
                idx = int(sel)
                if idx < 0 or idx >= len(self._invite_cache):
                    print("Invalid selection.")
                    return
            except ValueError:
                print("Invalid input.")
                return
            chosen = self._invite_cache[idx]
            rid = int(chosen['roomId'])
        else:
            rid = input("Room id to accept: ").strip()
            if not rid:
                print("No room id entered.")
                return
            try:
                rid = int(rid)
            except ValueError:
                print("Invalid room id.")
                return

        # 傳送接受邀請
        try:
            resp = self.lobby.send_request({'type': 'ACCEPT_INVITE', 'data': {'roomId': int(rid)}}, expected_types=['ACCEPT_INVITE_RESP'])
            data = resp.get('data', {})
            if data.get('ok'):
                print(f"✅ You joined room #{rid} successfully!")
                # 移除本地快取中已接受的邀請(s)
                try:
                    if self._invite_cache:
                        # remove by matching roomId (and optional fromUserId if chosen)
                        if 'chosen' in locals():
                            self._invite_cache.pop(idx)
                        else:
                            self._invite_cache = [i for i in self._invite_cache if i.get('roomId') != rid]
                except Exception:
                    pass
            else:
                error = data.get('error', 'Unknown error')
                if error == 'room not found':
                    print(f"❌ Room #{rid} no longer exists or has been closed.")
                elif error == 'room full':
                    print(f"❌ Room #{rid} is already full (2/2 players).")
                else:
                    print(f"❌ Accept failed: {error}")
        except Exception as e:
            print("Error:", e)

    def do_join_spectator(self):
        """Join a room as spectator to watch the game"""
        rid = input("Room ID to spectate: ").strip()
        if not rid:
            print("❌ Room ID required")
            return
        try:
            resp = self.lobby.send_request({'type':'JOIN_AS_SPECTATOR','data':{'roomId':int(rid)}})
            data = resp.get('data', {})
            if not data.get('ok'):
                print(f"❌ Failed to join as spectator: {data.get('error', 'unknown')}")
                return
            # Successfully got game server info
            host = data.get('host', '127.0.0.1')
            port = data.get('port')
            if not port:
                print("❌ No game server port provided")
                return
            print(f"✅ Joining game as spectator on {host}:{port}")
            # Launch GUI in spectator mode
            if not self.user:
                print("❌ Not logged in")
                return
            user_id = self.user['id']
            user_name = self.user.get('name', f'User{user_id}')
            # If game server host is localhost, use lobby's host instead (for remote connections)
            if host in ('127.0.0.1', 'localhost'):
                host = self.lobby.host
            try:
                self._in_game = True
                gui = GameClient(host, int(port), spectator=True, user_name=user_name)
                gui.run(user_id)
            finally:
                self._in_game = False
                self._game_done_event.set()
                # Clear push info to prevent auto-relaunch
                self._push_game_info = None
                self._pending_game_info = False
        except Exception as e:
            print(f"❌ Error joining as spectator: {e}")

    def do_start_game_and_play(self):
        rid=None
        if self.last_created_room_id:
            use_last=input(f"Start last created room #{self.last_created_room_id}? [Y/n] ").strip().lower()
            if use_last in ('','y','yes'): rid=self.last_created_room_id
        if not rid:
            rid=int(input("Room id to start: ").strip())

        # ask lobby to start room
        try:
            resp=self.lobby.send_request({'type':'START_ROOM','data':{'roomId':rid}}, expected_types=['START_ROOM_RESP'])
            data=resp.get('data',{})
            if not data.get('ok'):
                print("START failed:", data); return
            info=data  # might also get a GAME_SERVER_INFO push; use either
            host=info.get('host'); port=info.get('port'); mode=info.get('mode'); dur=info.get('durationSec')
            print(f"Game server: {host}:{port}  mode={mode} dur={dur}s")
        except TimeoutError:
            if not self._push_game_info:
                print("START timed out and no push arrived yet."); return
            host=self._push_game_info.get('host'); port=self._push_game_info.get('port')
            mode=self._push_game_info.get('mode'); dur=self._push_game_info.get('durationSec')
        # launch GUI (avoid double-launch if push already started it)
        if not self.user:
            print("Not logged in.")
            return
        user_id=self.user['id']
        
        # Check if already in game
        if self._in_game:
            # GUI already started by push handler; wait until it finishes to emulate blocking behavior
            print("Game already started; waiting for it to finish...")
            self._game_done_event.wait()
            return
        
        # Set _in_game BEFORE clearing pending flags to prevent race condition
        # where push handler might set _pending_game_info=True between clearing and starting
        self._in_game = True
        # clear any pending flag because we're about to launch GUI here
        self._pending_game_info = False
        self._push_game_info = None
        
        # otherwise start GUI in current thread (blocking)
        user_name = self.user.get('name', f'User{user_id}')
        # If game server host is localhost, use lobby's host instead (for remote connections)
        if host in ('127.0.0.1', 'localhost'):
            host = self.lobby.host
        try:
            gui = GameClient(host, int(port), user_name=user_name)
            gui.run(user_id)
        except Exception as e:
            print(f"[GUI] Failed to start GUI: {e}")
            # Make sure pygame is properly cleaned up on error
            try:
                pygame.quit()
            except:
                pass
        finally:
            self._in_game = False
            self._game_done_event.set()
            # Clear push info to prevent auto-relaunch
            self._push_game_info = None
            self._pending_game_info = False
            # Do not block here with input() — returning immediately allows
            # the main loop to handle incoming pushes (e.g. GAME_SERVER_INFO)
            # without being delayed by a blocking prompt which could cause
            # the GUI to be relaunched after the user finally presses Enter.
            print("Game finished. Returning to lobby...")

# ------------------------- entry -------------------------
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--lobby', default='127.0.0.1:13000', help='host:port of lobby server')
    args=ap.parse_args()
    lh, lp = args.lobby.split(':')
    app=ClientApp(lh, int(lp))
    app.run()

if __name__=='__main__':
    main()
