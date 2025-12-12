# lobby_server.py
import socket, threading, json, time, random, subprocess, os
from utils import send_msg, recv_msg

DB_HOST = "127.0.0.1"
DB_PORT = 12000
LOBBY_HOST = "0.0.0.0"  # Listen on all interfaces for remote connections
LOBBY_PORT = 13000

# Get the public hostname for Game Server connections
# Can be overridden with environment variable PUBLIC_HOST
# Default to linux4.cs.nycu.edu.tw for NYCU deployment
hostname = socket.gethostname()
if 'linux4' in hostname and 'cs.nycu.edu.tw' not in hostname:
    PUBLIC_HOST = 'linux4.cs.nycu.edu.tw'
else:
    PUBLIC_HOST = os.environ.get('PUBLIC_HOST', hostname)

# in-memory maps
clients = {}   # user_id -> (conn, addr, user)
rooms = {}     # room_id -> room dict
invitations = {} # user_id -> list of invite dicts
lock = threading.Lock()
_next_room_id = 1

# --------------------- DB bridge ---------------------
def db_call(msg: dict, timeout=5.0):
    """Send one msg to DB server and return the *entire* DB reply dict."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((DB_HOST, DB_PORT))
    send_msg(s, msg)
    resp = recv_msg(s)
    s.close()
    return resp

# --------------------- helpers -----------------------
def _new_room_id():
    global _next_room_id
    with lock:
        rid = _next_room_id
        _next_room_id += 1
    return rid

def _broadcast_room(room, payload):
    for uid in room['members']:
        if uid in clients:
            try: send_msg(clients[uid][0], payload)
            except: pass

def _spawn_game_server(rid, mode, durationSec):
    port = random.randint(10000, 20000)
    # game_server.py expects positional args: <port> <roomId> <mode> <durationSec>
    cmd = ["python3", "game_server.py", str(port), str(rid), mode, str(int(durationSec))]
    # 啟動後等待連得上再回
    subprocess.Popen(cmd)
    for _ in range(40):  # 最多約12秒
        try:
            t = socket.socket()
            t.settimeout(0.3)
            t.connect(("127.0.0.1", port))
            t.close()
            return port
        except:
            time.sleep(0.3)
    raise RuntimeError("game server not ready")

# --------------------- per-client thread -------------
def handle_client(conn, addr):
    print(f"[Lobby] Connected {addr}")
    user = None
    try:
        while True:
            try:
                req = recv_msg(conn)
            except Exception:
                break

            t = req.get('type'); d = req.get('data', {})

            # ---------- Register ----------
            if t == 'REGISTER':
                db_resp = db_call({'type':'REGISTER','data':d})
                # 重要：只轉發 DB 的 data，而不是整包
                send_msg(conn, {'type':'REGISTER_RESP','data': db_resp.get('data', {'ok':False,'error':'db error'})})

            # ---------- Login ----------
            elif t == 'LOGIN':
                db_resp = db_call({'type':'LOGIN','data':d})
                data = db_resp.get('data', {})
                if data.get('ok'):
                    candidate = data['user']
                    uid = candidate['id']
                    # Prevent duplicate login: if this user is already online, reject new login
                    with lock:
                        if uid in clients:
                            send_msg(conn, {'type':'LOGIN_RESP','data':{'ok':False,'error':'already_logged_in'}})
                            continue
                        user = candidate
                        clients[uid] = (conn, addr, user)
                send_msg(conn, {'type':'LOGIN_RESP','data': data})

            # ---------- Heartbeat ----------
            elif t == 'HEARTBEAT':
                if user:
                    db_call({'type':'HEARTBEAT','data':{'id':user['id']}})

            # ---------- Logout ----------
            elif t == 'LOGOUT':
                if user:
                    try:
                        db_call({'type':'LOGOUT','data':{'id':user['id']}})
                        # Remove from clients immediately upon logout
                        uid = user['id']
                        uname = user.get('name', f'User#{uid}')
                        with lock:
                            clients.pop(uid, None)
                            # Drop all rooms this user is in
                            dropped = []
                            for rid, room in list(rooms.items()):
                                if uid in room.get('members', []):
                                    dropped.append((rid, room))
                                    try:
                                        del rooms[rid]
                                    except KeyError:
                                        pass
                            # remove related invitations to dropped rooms
                            for target, invs in list(invitations.items()):
                                newlist = [i for i in invs if i.get('roomId') not in {r[0] for r in dropped}]
                                if newlist:
                                    invitations[target] = newlist
                                else:
                                    invitations.pop(target, None)
                        
                        if dropped:
                            print(f"[Lobby] User {uid} ({uname}) logged out, dropped rooms: {[r[0] for r in dropped]}")
                        else:
                            print(f"[Lobby] User {uid} ({uname}) logged out, no rooms dropped")
                        
                        # notify affected users and update DB status for dropped rooms
                        for rid, room in dropped:
                            # notify remaining members if online
                            for other in room.get('members', []):
                                if other == uid: continue
                                if other in clients:
                                    try:
                                        send_msg(clients[other][0], {'type':'ROOM_DROPPED','data':{'roomId': rid, 'reason': 'player_left'}})
                                    except Exception:
                                        pass
                            # update DB room status to 'closed' (best-effort) and remove related invites
                            try:
                                db_call({'type':'UPDATE_ROOM_STATUS','data':{'roomId':rid,'status':'closed'}})
                            except Exception:
                                pass
                            try:
                                # remove any outstanding invites related to this room
                                db_call({'type':'DELETE_INVITE','data':{'roomId':rid,'toUserId':None}})
                            except Exception:
                                pass
                        
                        send_msg(conn, {'type':'LOGOUT_RESP','data':{'ok':True}})
                    except Exception as e:
                        send_msg(conn, {'type':'LOGOUT_RESP','data':{'ok':False,'error':str(e)}})
                else:
                    send_msg(conn, {'type':'LOGOUT_RESP','data':{'ok':False,'error':'not logged in'}})

            # ---------- List online ----------
            elif t == 'LIST_ONLINE':
                # Return currently connected users from lobby_server's in-memory state
                # This is more accurate than relying on DB's lastSeenAt timestamps
                with lock:
                    online_user_ids = list(clients.keys())
                
                # Fetch totalScore from database for each online user
                online_users = []
                for uid in online_user_ids:
                    try:
                        db_resp = db_call({'type':'GET_USER','data':{'id':uid}})
                        user_data = db_resp.get('data',{}).get('user',{})
                        with lock:
                            # Double-check user is still online
                            if uid in clients:
                                online_users.append({
                                    'id': uid,
                                    'name': user_data.get('name', clients[uid][2].get('name', '?')),
                                    'totalScore': user_data.get('totalScore', 0),
                                    'totalLines': user_data.get('totalLines', 0)
                                })
                    except Exception:
                        # If DB call fails, still show the user without score
                        with lock:
                            if uid in clients:
                                online_users.append({
                                    'id': uid,
                                    'name': clients[uid][2].get('name', '?'),
                                    'totalScore': 0,
                                    'totalLines': 0
                                })
                
                send_msg(conn, {'type':'LIST_ONLINE_RESP','data':{'ok':True,'result':online_users}})

            # ---------- Create room ----------
            elif t == 'CREATE_ROOM':
                if not user:
                    send_msg(conn, {'type':'CREATE_ROOM_RESP','data':{'ok':False,'error':'not logged in'}})
                    continue
                # Persist room to DB and use DB-assigned id
                payload = {
                    'name': d.get('name', None) or f"room{int(time.time())}",
                    'hostUserId': user['id'],
                    'mode': d.get('mode','timed'),
                    'durationSec': int(d.get('durationSec',60)),
                    'visibility': d.get('visibility','public')
                }
                try:
                    db_resp = db_call({'type':'CREATE_ROOM','data': payload})
                except Exception as e:
                    send_msg(conn, {'type':'CREATE_ROOM_RESP','data':{'ok':False,'error':'db error'}}); continue
                data_db = db_resp.get('data', {})
                if not data_db.get('ok'):
                    send_msg(conn, {'type':'CREATE_ROOM_RESP','data':{'ok':False,'error': data_db.get('error','db create failed')}}); continue
                rid = data_db.get('result', {}).get('id')
                if not rid:
                    send_msg(conn, {'type':'CREATE_ROOM_RESP','data':{'ok':False,'error':'db returned no id'}}); continue

                room = {
                    'id': rid,
                    'name': payload['name'],
                    'hostUserId': payload['hostUserId'],
                    'mode': payload['mode'],
                    'durationSec': payload['durationSec'],
                    'members': [user['id']],
                    'status': 'idle',
                    'visibility': payload['visibility']
                }
                with lock:
                    rooms[rid] = room
                send_msg(conn, {'type':'CREATE_ROOM_RESP','data':{'ok':True,'result':{'id':rid}}})

            # ---------- List rooms (from DB) ----------
            elif t == 'LIST_ROOMS':
                try:
                    db_resp = db_call({'type':'LIST_ROOMS','data':{}})
                    data = db_resp.get('data', {})
                    if not data.get('ok'):
                        send_msg(conn, {'type':'LIST_ROOMS_RESP','data':{'ok':False,'error': data.get('error','db error')}})
                        continue
                    out = data.get('result', [])
                    # merge DB rooms into in-memory rooms (preserve 'playing' if already set locally)
                    with lock:
                        for r in out:
                            rid = r.get('id')
                            existing = rooms.get(rid)
                            room = {
                                'id': rid,
                                'name': r.get('name'),
                                'hostUserId': r.get('hostUserId'),
                                'mode': r.get('mode'),
                                'durationSec': r.get('durationSec'),
                                'members': r.get('memberList', []),
                                'status': existing['status'] if existing and existing.get('status')=='playing' else r.get('status','idle'),
                                'visibility': r.get('visibility','public')
                            }
                            rooms[rid] = room
                    send_msg(conn, {'type':'LIST_ROOMS_RESP','data':{'ok':True,'result':out}})
                except Exception as e:
                    send_msg(conn, {'type':'LIST_ROOMS_RESP','data':{'ok':False,'error':str(e)}})

            # ---------- Poll invites ----------
            elif t == 'POLL_INVITES':
                # Query invites from DB for logged-in user
                if not user:
                    send_msg(conn, {'type':'POLL_INVITES_RESP','data':{'ok':False,'error':'not logged in'}})
                    continue
                uid = user['id']
                try:
                    db_resp = db_call({'type':'LIST_INVITES','data':{'toUserId': uid}})
                    data = db_resp.get('data', {})
                    if data.get('ok'):
                        send_msg(conn, {'type':'POLL_INVITES_RESP','data':{'ok':True,'invites': data.get('result',[])}})
                    else:
                        send_msg(conn, {'type':'POLL_INVITES_RESP','data':{'ok':False,'error': data.get('error')}})
                except Exception as e:
                    send_msg(conn, {'type':'POLL_INVITES_RESP','data':{'ok':False,'error':str(e)}})

            # ---------- Invite ----------
            elif t == 'INVITE':
                if not user:
                    send_msg(conn, {'type':'INVITE_RESP','data':{'ok':False,'error':'not logged in'}}); continue
                rid = int(d.get('roomId',0)); tgt = int(d.get('targetUserId',0))
                with lock:
                    room = rooms.get(rid)
                if not room:
                    send_msg(conn, {'type':'INVITE_RESP','data':{'ok':False,'error':'room not found'}}); continue

                # persist invite to DB
                try:
                    db_call({'type':'CREATE_INVITE','data':{'roomId':rid,'fromUserId':user['id'],'toUserId':tgt}})
                except Exception:
                    pass

                inv = {'roomId': rid, 'roomName': room['name'], 'fromUserId': user['id'], 'fromUserName': user.get('name', '?'),
                       'mode': room['mode'], 'durationSec': room['durationSec'], 'ts': int(time.time())}

                # push if target online
                if tgt in clients:
                    try:
                        send_msg(clients[tgt][0], {'type':'INVITED','data':inv})
                    except:
                        pass
                    send_msg(conn, {'type':'INVITE_RESP','data':{'ok':True}})
                else:
                    # still return ok since invite is stored in DB for later
                    send_msg(conn, {'type':'INVITE_RESP','data':{'ok':True,'info':'target_offline_invited'}})

            # ---------- Join as Spectator ----------
            elif t == 'JOIN_AS_SPECTATOR':
                if not user:
                    send_msg(conn, {'type':'JOIN_AS_SPECTATOR_RESP','data':{'ok':False,'error':'not logged in'}}); continue
                rid = int(d.get('roomId',0))
                with lock:
                    room = rooms.get(rid)
                if not room:
                    send_msg(conn, {'type':'JOIN_AS_SPECTATOR_RESP','data':{'ok':False,'error':'room not found'}}); continue
                # Check if room is playing
                if room['status'] != 'playing':
                    send_msg(conn, {'type':'JOIN_AS_SPECTATOR_RESP','data':{'ok':False,'error':'room not started yet'}}); continue
                # Send game server info to spectator (no need to update room membership)
                # Game server info should already be available if room is playing
                # We need to find the game server port from the room's last broadcast
                # For simplicity, we'll send a GAME_SERVER_INFO push with the room's mode/duration
                # and let the spectator connect to the game server dynamically
                # However, we don't store the game server port in the room object.
                # Solution: Let the spectator query the room host or store port in room dict.
                # For now, return error if we can't provide server info
                # Better approach: store game_port in room when START_ROOM succeeds
                game_port = room.get('game_port')
                if not game_port:
                    send_msg(conn, {'type':'JOIN_AS_SPECTATOR_RESP','data':{'ok':False,'error':'game server info not available'}}); continue
                # Use the server's public hostname/IP instead of 127.0.0.1
                info = {'host':PUBLIC_HOST,'port':game_port,'mode':room['mode'],'durationSec':room['durationSec'],'spectator':True}
                send_msg(conn, {'type':'JOIN_AS_SPECTATOR_RESP','data':{'ok':True, **info}})

            # ---------- Accept invite ----------
            elif t == 'ACCEPT_INVITE':
                if not user:
                    send_msg(conn, {'type':'ACCEPT_INVITE_RESP','data':{'ok':False,'error':'not logged in'}}); continue
                rid = int(d.get('roomId',0))
                uid = user['id']
                
                # First, find and leave any existing rooms (player can only be in one room at a time)
                old_rooms_to_leave = []
                with lock:
                    for old_rid, old_room in rooms.items():
                        if old_rid != rid and uid in old_room['members']:
                            old_rooms_to_leave.append((old_rid, old_room))
                
                # Leave old rooms and notify their hosts
                for old_rid, old_room in old_rooms_to_leave:
                    old_host_id = old_room.get('hostUserId')
                    old_room_name = old_room.get('name', f'Room#{old_rid}')
                    print(f"[Lobby] User {uid} ({user.get('name')}) leaving room {old_rid} to join room {rid}")
                    
                    # Remove from room members
                    with lock:
                        if old_rid in rooms and uid in rooms[old_rid]['members']:
                            rooms[old_rid]['members'].remove(uid)
                    
                    # Remove from DB
                    try:
                        db_call({'type':'REMOVE_MEMBER','data':{'roomId':old_rid,'userId':uid}})
                    except Exception as e:
                        print(f"[Lobby] Failed to remove member from DB: {e}")
                    
                    # Notify old host that member left
                    if old_host_id and old_host_id != uid:
                        with lock:
                            if old_host_id in clients:
                                try:
                                    drop_msg = {
                                        'type': 'ROOM_DROPPED',
                                        'data': {
                                            'roomId': old_rid,
                                            'roomName': old_room_name,
                                            'reason': f"{user.get('name', f'User#{uid}')} left to join another room"
                                        }
                                    }
                                    send_msg(clients[old_host_id][0], drop_msg)
                                    print(f"[Lobby] ✅ Notified host {old_host_id} ({clients[old_host_id][2].get('name')}) that {user.get('name')} left room {old_rid}")
                                except Exception as e:
                                    print(f"[Lobby] ❌ Failed to notify old host {old_host_id}: {e}")
                            else:
                                print(f"[Lobby] Old host {old_host_id} is offline, skipping notification")
                
                # Now join the new room
                with lock:
                    room = rooms.get(rid)
                    if not room:
                        send_msg(conn, {'type':'ACCEPT_INVITE_RESP','data':{'ok':False,'error':'room not found'}}); continue
                    if uid not in room['members']:
                        if len(room['members']) >= 2:
                            send_msg(conn, {'type':'ACCEPT_INVITE_RESP','data':{'ok':False,'error':'room full'}}); continue
                        room['members'].append(uid)
                # persist membership to DB as well
                try:
                    db_call({'type':'ADD_MEMBER','data':{'roomId':rid,'userId':uid}})
                except Exception:
                    pass
                # remove invite(s) from DB
                try:
                    db_call({'type':'DELETE_INVITE','data':{'roomId':rid,'toUserId':uid}})
                except Exception:
                    pass
                # also clean local cache if present
                try:
                    if uid in invitations:
                        invitations.pop(uid, None)
                except Exception:
                    pass
                
                # Notify room host that someone joined (do this BEFORE sending response)
                host_id = None
                room_name = None
                member_count = 0
                with lock:
                    room = rooms.get(rid)
                    if room:
                        host_id = room.get('hostUserId')
                        room_name = room.get('name')
                        member_count = len(room.get('members', []))
                
                if host_id and host_id != uid:
                    with lock:
                        if host_id in clients:
                            try:
                                join_msg = {
                                    'type': 'MEMBER_JOINED',
                                    'data': {
                                        'roomId': rid,
                                        'roomName': room_name,
                                        'userId': uid,
                                        'userName': user.get('name', f'User#{uid}'),
                                        'memberCount': member_count
                                    }
                                }
                                send_msg(clients[host_id][0], join_msg)
                                print(f"[Lobby] ✅ Sent MEMBER_JOINED notification to host {host_id} ({clients[host_id][2].get('name')}) for room {rid}")
                            except Exception as e:
                                print(f"[Lobby] ❌ Failed to notify host {host_id}: {e}")
                
                send_msg(conn, {'type':'ACCEPT_INVITE_RESP','data':{'ok':True}})

            # ---------- Start room ----------
            elif t == 'START_ROOM':
                if not user:
                    send_msg(conn, {'type':'START_ROOM_RESP','data':{'ok':False,'error':'not logged in'}}); continue
                rid = int(d.get('roomId',0))
                with lock:
                    room = rooms.get(rid)
                if not room:
                    send_msg(conn, {'type':'START_ROOM_RESP','data':{'ok':False,'error':'room not found'}}); continue
                if room['hostUserId'] != user['id']:
                    send_msg(conn, {'type':'START_ROOM_RESP','data':{'ok':False,'error':'not host'}}); continue
                if len(room['members']) < 2:
                    send_msg(conn, {'type':'START_ROOM_RESP','data':{'ok':False,'error':'need 2 players'}}); continue

                try:
                    port=_spawn_game_server(rid,room['mode'],room['durationSec'])
                except Exception as e:
                    send_msg(conn, {'type':'START_ROOM_RESP','data':{'ok':False,'error':str(e)}}); continue
                print(f"[Lobby] Started game server for room {rid} on port {port} mode={room['mode']} dur={room['durationSec']} members={room['members']}")
                # Use the server's public hostname/IP instead of 127.0.0.1
                info = {'host':PUBLIC_HOST,'port':port,'mode':room['mode'],'durationSec':room['durationSec']}
                room['status'] = 'playing'
                room['game_port'] = port  # Store game server port for spectators
                _broadcast_room(room, {'type':'GAME_SERVER_INFO','data':info})
                send_msg(conn, {'type':'START_ROOM_RESP','data':{'ok':True, **info}})

            # ---------- Game over report from game server ----------
            elif t == 'GAME_OVER_REPORT':
                # best-effort: persist a gamelog entry to DB and mark room closed
                d = req.get('data', {})
                roomId = int(d.get('roomId', 0))
                results = d.get('results', [])
                mode = d.get('mode', 'timed')
                duration = int(d.get('durationSec', d.get('duration', 0) or 0))
                # determine winner/loser based on mode
                winner = None; loser = None
                try:
                    if results:
                        if mode == 'survival':
                            # Survival mode: winner is the player who is still alive
                            # If no one is alive (both died), winner is determined by score/lines
                            alive_players = [r for r in results if r.get('alive', False)]
                            if alive_players:
                                # Winner is the survivor
                                winner = alive_players[0].get('userId')
                                # Loser is anyone who died
                                for r in results:
                                    if not r.get('alive', False):
                                        loser = r.get('userId')
                                        break
                            else:
                                # Both died, use score/lines
                                best = max(results, key=lambda r: (r.get('lines', 0), r.get('score', 0)))
                                winner = best.get('userId')
                                loser = next((r.get('userId') for r in results if r.get('userId') != winner), None)
                        else:
                            # Timed mode: prefer higher lines, then higher score
                            best = max(results, key=lambda r: (r.get('lines', 0), r.get('score', 0)))
                            winner = best.get('userId')
                            loser = next((r.get('userId') for r in results if r.get('userId') != winner), None)
                except Exception as e:
                    print(f"[Lobby] Error determining winner: {e}")
                    winner = None; loser = None
                # persist to DB via db_call
                try:
                    # include full results so DB can persist per-player scores/lines
                    db_call({'type':'ADD_GAMELOG','data':{'roomId': roomId, 'winnerId': winner, 'loserId': loser, 'duration': duration, 'mode': mode, 'results': results}})
                except Exception:
                    pass
                # mark room closed in DB (best-effort)
                try:
                    db_call({'type':'UPDATE_ROOM_STATUS','data':{'roomId': roomId, 'status':'closed'}})
                except Exception:
                    pass
                # reply ack to game server
                try:
                    send_msg(conn, {'type':'GAME_OVER_REPORT_RESP','data':{'ok':True}})
                except Exception:
                    pass

            else:
                send_msg(conn, {'type':'ERROR','data':{'ok':False,'error':f'unknown type {t}'}})

    except Exception as e:
        print("[Lobby] Error:", e)
    finally:
        # 清理線上列表
        if user:
            # Mark user as offline in DB when they disconnect
            try:
                db_call({'type':'LOGOUT','data':{'id': user['id']}})
            except Exception:
                pass
            uid = user['id']
            uname = user.get('name', f'User#{uid}')
            with lock:
                clients.pop(uid, None)
                # If this user was member of any room, drop that room entirely
                dropped = []
                for rid, room in list(rooms.items()):
                    if uid in room.get('members', []):
                        dropped.append((rid, room))
                        try:
                            del rooms[rid]
                        except KeyError:
                            pass
                # remove related invitations to dropped rooms
                for target, invs in list(invitations.items()):
                    newlist = [i for i in invs if i.get('roomId') not in {r[0] for r in dropped}]
                    if newlist:
                        invitations[target] = newlist
                    else:
                        invitations.pop(target, None)
            if dropped:
                print(f"[Lobby] User {uid} ({uname}) disconnected, dropped rooms: {[r[0] for r in dropped]}")
            else:
                print(f"[Lobby] User {uid} ({uname}) disconnected, no rooms dropped")
            # notify affected users and update DB status for dropped rooms
            for rid, room in dropped:
                # notify remaining members if online
                for other in room.get('members', []):
                    if other == uid: continue
                    if other in clients:
                        try:
                            send_msg(clients[other][0], {'type':'ROOM_DROPPED','data':{'roomId': rid, 'reason': 'player_left'}})
                        except Exception:
                            pass
                # update DB room status to 'closed' (best-effort) and remove related invites
                try:
                    db_call({'type':'UPDATE_ROOM_STATUS','data':{'roomId':rid,'status':'closed'}})
                except Exception:
                    pass
                try:
                    # remove any outstanding invites related to this room
                    db_call({'type':'DELETE_INVITE','data':{'roomId':rid,'toUserId':None}})
                except Exception:
                    pass
        try: conn.close()
        except: pass
        print(f"[Lobby] Disconnected {addr}")

# --------------------- main -------------------------
def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((LOBBY_HOST, LOBBY_PORT)); s.listen(16)
    print(f"[Lobby] Listening on {LOBBY_HOST}:{LOBBY_PORT}")
    while True:
        c,a = s.accept()
        threading.Thread(target=handle_client, args=(c,a), daemon=True).start()

if __name__ == '__main__':
    main()
