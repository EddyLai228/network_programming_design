# game_server.py
# Usage: python game_server.py <port> <roomId> <mode: timed|survival> <durationSec>
import socket, threading, time, sys, random
from utils import recv_msg, send_msg

# ---------- Args ----------
HOST='0.0.0.0'  # Listen on all interfaces for remote connections
if len(sys.argv) < 5:
    print("usage: python game_server.py <port> <roomId> <mode:timed|survival> <durationSec>")
    sys.exit(1)
PORT=int(sys.argv[1]); ROOM_ID=int(sys.argv[2])
MODE=sys.argv[3]; DURATION=int(sys.argv[4])

# ---------- Tetris core ----------
BOARD_W, BOARD_H = 10, 20
TICK_MS=50
SNAPSHOT_INTERVAL=0.10
GRAVITY_MS=1000
LOCK_DELAY_MS=500
BAG = ['I','O','T','J','L','S','Z']
SCORES = {0:0,1:100,2:300,3:500,4:800}

TET = {
 'I':[[(0,1),(1,1),(2,1),(3,1)],[(2,0),(2,1),(2,2),(2,3)],[(0,2),(1,2),(2,2),(3,2)],[(1,0),(1,1),(1,2),(1,3)]],
 'O':[[(1,0),(2,0),(1,1),(2,1)]]*4,
 'T':[[(1,0),(0,1),(1,1),(2,1)],[(1,0),(1,1),(2,1),(1,2)],[(0,1),(1,1),(2,1),(1,2)],[(1,0),(0,1),(1,1),(1,2)]],
 'J':[[(0,0),(0,1),(1,1),(2,1)],[(1,0),(2,0),(1,1),(1,2)],[(0,1),(1,1),(2,1),(2,2)],[(1,0),(1,1),(0,2),(1,2)]],
 'L':[[(2,0),(0,1),(1,1),(2,1)],[(1,0),(1,1),(1,2),(2,2)],[(0,1),(1,1),(2,1),(0,2)],[(0,0),(1,0),(1,1),(1,2)]],
 'S':[[(1,0),(2,0),(0,1),(1,1)],[(1,0),(1,1),(2,1),(2,2)],[(1,1),(2,1),(0,2),(1,2)],[(0,0),(0,1),(1,1),(1,2)]],
 'Z':[[(0,0),(1,0),(1,1),(2,1)],[(2,0),(1,1),(2,1),(1,2)],[(0,1),(1,1),(1,2),(2,2)],[(1,0),(0,1),(1,1),(0,2)]],
}

def empty_board(): return [['.' for _ in range(BOARD_W)] for __ in range(BOARD_H)]
def cells(shape, rot, x, y): return [(x+cx, y+cy) for (cx,cy) in TET[shape][rot%len(TET[shape])]]
def inb(x,y): return 0<=x<BOARD_W and 0<=y<BOARD_H
def collide(board, shape, rot, x, y):
    for (xx,yy) in cells(shape,rot,x,y):
        if yy < 0: continue
        if not inb(xx,yy) or board[yy][xx] != '.': return True
    return False
def line_clear(board):
    cleared=0; nb=[]
    for row in board:
        if all(c!='.' for c in row): cleared+=1
        else: nb.append(row)
    for _ in range(cleared): nb.insert(0,['.' for _ in range(BOARD_W)])
    return nb, cleared
def lock_piece(board, shape, rot, x, y):
    for (xx,yy) in cells(shape,rot,x,y):
        if 0<=yy<BOARD_H and 0<=xx<BOARD_W: board[yy][xx]=shape
    new_board, cleared = line_clear(board)
    # detect top-out: if any cell in the top row is filled after locking, caller
    # should mark the player as dead in survival mode. We return the board and
    # cleared count; callers will check the top row and set 'alive'=False when needed.
    return new_board, cleared

def spawn(state, check_topout=True):
    global shared_bag
    refill_shared_bag()
    state['shape'] = shared_bag.pop(0)  # Take from shared bag
    state['rot']=0; state['x']=3; state['y']=-1
    if state['next']: state['next'].pop(0)
    while len(state['next'])<5:
        refill_shared_bag()
        state['next'].append(shared_bag[0])
    # Top-out detection: check if any part of the new piece that would be in bounds
    # overlaps with existing blocks, indicating the playfield is full
    # Skip this check during initial spawn (board is empty)
    if check_topout:
        for (cx, cy) in cells(state['shape'], state['rot'], state['x'], state['y']):
            # Only check cells that are within the visible board
            if 0 <= cy < BOARD_H and 0 <= cx < BOARD_W:
                if state['board'][cy][cx] != '.':
                    state['alive'] = False
                    return

def rotate_kick(board,state):
    new=(state['rot']+1)%4
    for dx in [0,-1,1,-2,2]:
        if not collide(board,state['shape'],new,state['x']+dx,state['y']):
            state['rot']=new; state['x']+=dx; return

def hard_drop(state):
    y=state['y']
    while not collide(state['board'],state['shape'],state['rot'],state['x'],y+1):
        y+=1
    state['y']=y
    state['board'],cleared=lock_piece(state['board'],state['shape'],state['rot'],state['x'],state['y'])
    state['score']+=SCORES.get(cleared,0); state['lines']+=cleared
    # top-out detection: if any block occupies the top 2 rows after locking, mark dead
    # Standard Tetris: game over if blocks reach the spawn zone (top rows)
    try:
        if any(c != '.' for c in state['board'][0]) or any(c != '.' for c in state['board'][1]):
            state['alive'] = False
    except Exception:
        pass
    state['lock_until']=None; spawn(state)

def soft_one(state):
    if not collide(state['board'],state['shape'],state['rot'],state['x'],state['y']+1):
        state['y']+=1; state['score']+=1

def move_x(state,dx):
    nx=state['x']+dx
    if not collide(state['board'],state['shape'],state['rot'],nx,state['y']): state['x']=nx

def try_lock(state, now_ms):
    if collide(state['board'],state['shape'],state['rot'],state['x'],state['y']+1):
        if state['lock_until'] is None: state['lock_until']=now_ms+LOCK_DELAY_MS
        elif now_ms>=state['lock_until']:
            state['board'],cleared=lock_piece(state['board'],state['shape'],state['rot'],state['x'],state['y'])
            state['score']+=SCORES.get(cleared,0); state['lines']+=cleared
            # top-out detection after locking
            try:
                if any(c != '.' for c in state['board'][0]) or any(c != '.' for c in state['board'][1]):
                    state['alive'] = False
            except Exception:
                pass
            state['lock_until']=None; spawn(state)
    else:
        state['lock_until']=None

# ---------- Server state ----------
lock=threading.Lock()
clients={}        # conn -> pid
conns={}          # pid -> conn
states={}         # pid -> state
spectators={}     # conn -> spectator_info (userId, name)
inputs=[]         # (pid,msg)
start_ms = int(time.time()*1000)
ended=False
# Shared bag for all players (7-bag + Fisher-Yates)
shared_bag = []

def refill_shared_bag():
    """Refill the shared bag with a shuffled set of all 7 pieces (Fisher-Yates)"""
    global shared_bag
    if not shared_bag:
        b = BAG[:]
        random.shuffle(b)  # Fisher-Yates shuffle
        shared_bag.extend(b)
        print(f"[Game] Refilled shared bag: {shared_bag}")

def init_player(pid):
    st={'id':pid,'board':empty_board(),'next':[],'shape':None,'rot':0,'x':3,'y':-1,
        'score':0,'lines':0,'level':1,'alive':True,'last_drop':int(time.time()*1000),
        'drop_ms':GRAVITY_MS,'lock_until':None}
    # Fill next preview from shared bag
    for _ in range(5):
        refill_shared_bag()
        st['next'].append(shared_bag[0])
    spawn(st, check_topout=False); return st  # Don't check topout on initial spawn (board is empty)

# ---------- Networking ----------
def build_snap(pid):
    st=states.get(pid)
    if not st: return None
    return {'type':'SNAPSHOT','tick':int(time.time()*1000),'userId':pid,'board':st['board'],
            'active':{'shape':st['shape'],'x':st['x'],'y':st['y'],'rot':st['rot']},
            'next':st['next'][:3],'score':st['score'],'lines':st['lines'],
            'alive':st['alive'],'mode':MODE,'durationSec':DURATION,
            'at':int(time.time()*1000)}

def broadcast(obj):
    dead=[]
    # Send to players
    for c in list(clients.keys()):
        try: send_msg(c,obj)
        except Exception: dead.append(c)
    # Send to spectators
    for c in list(spectators.keys()):
        try: send_msg(c,obj)
        except Exception: dead.append(c)
    for c in dead:
        pid=clients.get(c)
        try: c.close()
        except: pass
        with lock:
            if c in clients: del clients[c]
            if c in spectators: del spectators[c]
            if pid in conns: del conns[pid]
            if pid in states: del states[pid]

def end_and_report():
    global ended
    if ended: return
    ended=True
    # results: 比 lines（計時賽）；存活制比 alive/lines
    res=[]
    for pid,st in states.items():
        res.append({'userId':pid,'score':st['score'],'lines':st['lines']})
    # prepare a report mapping to real user ids (if client provided via HELLO)
    report_results = []
    for pid,st in states.items():
        real_uid = st.get('userId', pid)
        # In survival mode, include alive status for proper winner determination
        result_entry = {'userId': real_uid, 'score': st['score'], 'lines': st['lines']}
        if MODE == 'survival':
            result_entry['alive'] = st['alive']
        report_results.append(result_entry)
        print(f"[Game] Reporting: pid={pid} -> real_uid={real_uid}, score={st['score']}, lines={st['lines']}, alive={st['alive']}")
    # broadcast GAME_OVER
    broadcast({'type':'GAME_OVER','data':{'roomId':ROOM_ID,'mode':MODE,'durationSec':DURATION,'results':res}})
    # 回報 Lobby
    try:
        s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        s.connect(('127.0.0.1',13000))
        send_msg(s, {'type':'GAME_OVER_REPORT','data':{
            'matchId': str(int(time.time())),
            'roomId': ROOM_ID,
            'users': [st.get('userId', pid) for pid,st in states.items()],
            'startAt': start_ms//1000,
            'endAt': int(time.time()),
            'mode': MODE,
            'durationSec': DURATION,
            'results': report_results
        }})
        s.close()
    except Exception:
        pass

def handle_client(conn, addr):
    try:
        hello=recv_msg(conn)
    except Exception:
        conn.close(); return
    if hello.get('type')!='HELLO':
        send_msg(conn, {'type':'ERR','error':'expected HELLO'}); conn.close(); return
    
    # Check if this is a spectator connection
    is_spectator = hello.get('spectator', False)
    
    if is_spectator:
        # Handle spectator connection - no game state, just watch
        with lock:
            spectators[conn] = {'userId': hello.get('userId'), 'name': hello.get('userName', 'Spectator')}
            # Build players info for spectator
            players_info = {}
            for p, st in states.items():
                players_info[p] = {
                    'userId': st.get('userId', p),
                    'userName': st.get('userName', f'Player{p+1}')
                }
        send_msg(conn, {'type':'WELCOME','role':'SPECTATOR','mode':MODE,'durationSec':DURATION,'players':players_info})
        print(f"[Game] Spectator connected: userId={hello.get('userId')}")
        # Spectator just receives snapshots, send them current state immediately
        with lock:
            for pid in list(states.keys()):
                snap=build_snap(pid)
                if snap:
                    try: send_msg(conn, snap)
                    except: pass
        # Keep connection open to receive future snapshots
        try:
            while True:
                # Spectators don't send INPUT, just keep connection alive
                msg=recv_msg(conn)
                # Ignore any messages from spectators
        except Exception:
            pass
        finally:
            with lock:
                if conn in spectators: del spectators[conn]
            try: conn.close()
            except: pass
        return
    
    # Handle player connection
    with lock:
        if len(states)>=2: send_msg(conn,{'type':'ERR','error':'room full'}); conn.close(); return
        pid=0
        while pid in states: pid+=1
        clients[conn]=pid; conns[pid]=conn; states[pid]=init_player(pid)
    # record client's real user id and name if provided in HELLO (do this after init)
    try:
        real_uid = hello.get('userId')
        user_name = hello.get('userName')
        if real_uid is not None:
            with lock:
                states[pid]['userId'] = real_uid
                if user_name:
                    states[pid]['userName'] = user_name
            print(f"[Game] Recorded real userId={real_uid} name={user_name} for pid={pid}")
        else:
            print(f"[Game] WARNING: No userId in HELLO for pid={pid}")
    except Exception as e:
        print(f"[Game] ERROR recording userId for pid={pid}: {e}")
    
    # Build players info for WELCOME message
    players_info = {}
    with lock:
        for p, st in states.items():
            players_info[p] = {
                'userId': st.get('userId', p),
                'userName': st.get('userName', f'Player{p+1}')
            }
    
    send_msg(conn, {'type':'WELCOME','role':f'P{pid+1}','seed':random.randint(1,10**9),
                    'bagRule':'7bag','gravityPlan':{'mode':'fixed','dropMs':GRAVITY_MS},
                    'mode':MODE,'durationSec':DURATION,'players':players_info})
    print(f"[Game] Sent WELCOME to pid={pid} role=P{pid+1} mode={MODE} dur={DURATION}")
    
    # Broadcast updated player list to all existing players (so they know about the new player)
    if len(states) > 1:
        with lock:
            updated_players_info = {}
            for p, st in states.items():
                updated_players_info[p] = {
                    'userId': st.get('userId', p),
                    'userName': st.get('userName', f'Player{p+1}')
                }
        # Send PLAYER_UPDATE to all other connected players
        for other_pid, other_conn in list(conns.items()):
            if other_pid != pid:
                try:
                    send_msg(other_conn, {'type':'PLAYER_UPDATE','players':updated_players_info})
                    print(f"[Game] Sent PLAYER_UPDATE to pid={other_pid}")
                except Exception:
                    pass
    try:
        while True:
            msg=recv_msg(conn)
            if msg.get('type')=='INPUT':
                with lock: inputs.append((pid,msg))
    except Exception:
        pass
    finally:
        with lock:
            if conn in clients:
                p=clients[conn]; del clients[conn]
                if p in conns: del conns[p]
                if p in states: del states[p]
        try: conn.close()
        except: pass

def game_loop():
    global ended
    last=time.time(); last_snap=time.time()
    while True:
        now=time.time(); delta=(now-last)*1000; last=now
        with lock:
            # apply inputs
            while inputs:
                pid,msg=inputs.pop(0)
                if pid in states and states[pid]['alive']:
                    a=msg.get('action','').upper()
                    st=states[pid]
                    if a=='LEFT': move_x(st,-1)
                    elif a=='RIGHT': move_x(st,1)
                    elif a=='ROT': rotate_kick(st['board'],st)
                    elif a=='SOFT': soft_one(st)
                    elif a=='DROP': hard_drop(st)
                    st['lock_until']=None
            # physics
            ms=int(time.time()*1000)
            for st in states.values():
                if not st['alive']: continue
                if ms - st['last_drop'] >= st['drop_ms']:
                    st['last_drop']=ms
                    if not collide(st['board'],st['shape'],st['rot'],st['x'],st['y']+1):
                        st['y']+=1
                    else:
                        try_lock(st, ms)
                else:
                    try_lock(st, ms)
            # 判斷結束
            if MODE=='timed':
                if (ms - start_ms) >= DURATION*1000:
                    end_and_report()
            else:  # survival
                alive=[st for st in states.values() if st['alive']]
                # Game ends when:
                # 1. All players are dead (len(alive)==0), OR
                # 2. Only one survivor remains in a multi-player game (len(states)>=2 and len(alive)==1)
                if len(states) >= 2 and len(alive) <= 1:
                    end_and_report()
                elif len(states) == 1 and len(alive) == 0:
                    # Single player died
                    end_and_report()
        # snapshot
        if time.time()-last_snap >= SNAPSHOT_INTERVAL:
            with lock:
                for pid in list(states.keys()):
                    snap=build_snap(pid)
                    if snap: broadcast(snap)
            last_snap=time.time()
        time.sleep(TICK_MS/1000.0)

def main():
    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    s.bind((HOST,PORT)); s.listen(4)
    print(f"Game server on {HOST}:{PORT} room={ROOM_ID} mode={MODE} dur={DURATION}s")
    threading.Thread(target=game_loop, daemon=True).start()
    try:
        while True:
            c,a=s.accept()
            threading.Thread(target=handle_client, args=(c,a), daemon=True).start()
    finally:
        s.close()

if __name__=='__main__':
    main()
