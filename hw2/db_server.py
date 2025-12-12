# db_server.py
# Central DB microservice for Tetris system.
# Supports users, rooms, and game logs.

import socket, threading, sqlite3, time, hashlib
from utils import send_msg, recv_msg

HOST = '0.0.0.0'  # Listen on all interfaces for remote connections
PORT = 12000
DBPATH = 'tetris_demo.db'

# ------------------ Utility ------------------
def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode('utf-8')).hexdigest()

def ts() -> int:
    return int(time.time())

# ------------------ Schema ------------------
def init_db():
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    # users
    c.execute('''CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        passwordHash TEXT,
        createdAt INTEGER,
        lastLoginAt INTEGER,
        lastSeenAt INTEGER,
        totalScore INTEGER,
        totalLines INTEGER
    )''')
    # rooms
    c.execute('''CREATE TABLE IF NOT EXISTS rooms(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        hostUserId INTEGER,
        mode TEXT,
        durationSec INTEGER,
        visibility TEXT,
        status TEXT,
        createdAt INTEGER
    )''')
    # room_members
    c.execute('''CREATE TABLE IF NOT EXISTS room_members(
        roomId INTEGER,
        userId INTEGER
    )''')
    # invitations
    c.execute('''CREATE TABLE IF NOT EXISTS invitations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roomId INTEGER,
        fromUserId INTEGER,
        toUserId INTEGER,
        ts INTEGER
    )''')
    # game logs
    c.execute('''CREATE TABLE IF NOT EXISTS gamelogs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roomId INTEGER,
        winnerId INTEGER,
        loserId INTEGER,
        finishedAt INTEGER,
        duration INTEGER,
        mode TEXT
    )''')
    # per-game player results (score/lines)
    c.execute('''CREATE TABLE IF NOT EXISTS gamelog_players(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gamelogId INTEGER,
        userId INTEGER,
        score INTEGER,
        lines INTEGER
    )''')
    conn.commit()
    conn.close()
    print("[DB] Schema ready (users, rooms, gamelogs).")

# ------------------ Command handlers ------------------
def handle_cmd(cur, msg):
    t = msg.get('type')
    d = msg.get('data', {})

    # -------- USERS --------
    if t == 'REGISTER':
        name, pw = d.get('name'), d.get('password')
        if not name or not pw:
            return {'type': 'REGISTER_RESP', 'data': {'ok': False, 'error': 'missing fields'}}
        try:
            cur.execute("INSERT INTO users (name,passwordHash,createdAt,lastLoginAt,lastSeenAt) VALUES (?,?,?,?,?)",
                        (name, hash_pw(pw), ts(), 0, 0))
            return {'type': 'REGISTER_RESP', 'data': {'ok': True, 'result': {'id': cur.lastrowid}}}
        except sqlite3.IntegrityError:
            return {'type': 'REGISTER_RESP', 'data': {'ok': False, 'error': 'name exists'}}

    if t == 'LOGIN':
        name, pw = d.get('name'), d.get('password')
        cur.execute("SELECT id,name,passwordHash FROM users WHERE name=?", (name,))
        r = cur.fetchone()
        if not r: return {'type': 'LOGIN_RESP', 'data': {'ok': False, 'error': 'user not found'}}
        if r[2] != hash_pw(pw):
            return {'type': 'LOGIN_RESP', 'data': {'ok': False, 'error': 'bad password'}}
        now = ts()
        cur.execute("UPDATE users SET lastLoginAt=?, lastSeenAt=? WHERE id=?", (now, now, r[0]))
        return {'type': 'LOGIN_RESP', 'data': {'ok': True, 'user': {'id': r[0], 'name': r[1]}}}

    if t == 'GET_USER':
        uid = d.get('id')
        cur.execute("SELECT id,name,totalScore,totalLines FROM users WHERE id=?", (uid,))
        r = cur.fetchone()
        if not r:
            return {'type': 'GET_USER_RESP', 'data': {'ok': False, 'error': 'user not found'}}
        user_data = {
            'id': r[0],
            'name': r[1],
            'totalScore': r[2] if r[2] is not None else 0,
            'totalLines': r[3] if r[3] is not None else 0
        }
        return {'type': 'GET_USER_RESP', 'data': {'ok': True, 'user': user_data}}

    if t == 'HEARTBEAT':
        uid = d.get('id', d.get('userId'))
        cur.execute("UPDATE users SET lastSeenAt=? WHERE id=?", (ts(), uid))
        return {'type': 'HEARTBEAT_RESP', 'data': {'ok': True}}

    if t == 'LOGOUT':
        uid = d.get('id', d.get('userId'))
        # Set lastSeenAt to 0 to mark user as offline
        cur.execute("UPDATE users SET lastSeenAt=? WHERE id=?", (0, uid))
        return {'type': 'LOGOUT_RESP', 'data': {'ok': True}}

    if t == 'LIST_ONLINE':
        cur.execute("SELECT id,name,lastSeenAt FROM users WHERE lastSeenAt >= ?", (ts() - 120,))
        rows = [{'id': r[0], 'name': r[1], 'lastSeenAt': r[2]} for r in cur.fetchall()]
        return {'type': 'LIST_ONLINE_RESP', 'data': {'ok': True, 'result': rows}}

    # -------- ROOMS --------
    if t == 'CREATE_ROOM':
        name = d.get('name', f"room{int(time.time())}")
        cur.execute("""INSERT INTO rooms(name,hostUserId,mode,durationSec,visibility,status,createdAt)
                       VALUES(?,?,?,?,?,?,?)""",
                    (name, d.get('hostUserId'), d.get('mode','timed'), d.get('durationSec',60),
                     d.get('visibility','public'), 'idle', ts()))
        rid = cur.lastrowid
        cur.execute("INSERT INTO room_members(roomId,userId) VALUES(?,?)", (rid, d.get('hostUserId')))
        return {'type': 'CREATE_ROOM_RESP', 'data': {'ok': True, 'result': {'id': rid}}}

    if t == 'LIST_ROOMS':
        cur.execute("SELECT id,name,hostUserId,mode,durationSec,visibility,status FROM rooms ORDER BY id DESC")
        rooms = []
        for r in cur.fetchall():
            cur.execute("SELECT userId FROM room_members WHERE roomId=?", (r[0],))
            members = [m[0] for m in cur.fetchall()]
            rooms.append({
                'id': r[0], 'name': r[1], 'hostUserId': r[2],
                'mode': r[3], 'durationSec': r[4], 'visibility': r[5],
                'status': r[6], 'memberList': members
            })
        return {'type': 'LIST_ROOMS_RESP', 'data': {'ok': True, 'result': rooms}}

    # ---------- INVITATIONS ----------
    if t == 'CREATE_INVITE':
        cur.execute("INSERT INTO invitations(roomId,fromUserId,toUserId,ts) VALUES(?,?,?,?)",
                    (d.get('roomId'), d.get('fromUserId'), d.get('toUserId'), ts()))
        return {'type': 'CREATE_INVITE_RESP', 'data': {'ok': True, 'result': {'id': cur.lastrowid}}}

    if t == 'LIST_INVITES':
        # expects data: { toUserId: <id> }
        to_uid = d.get('toUserId')
        if to_uid is None:
            return {'type': 'LIST_INVITES_RESP', 'data': {'ok': False, 'error': 'missing toUserId'}}
        cur.execute("SELECT id,roomId,fromUserId,ts FROM invitations WHERE toUserId=? ORDER BY ts DESC", (to_uid,))
        rows = cur.fetchall()
        out = []
        invites_to_delete = []  # track closed room invites to clean up
        for r in rows:
            iid, rid, frm, tts = r
            # fetch room metadata including status
            cur.execute("SELECT name,mode,durationSec,status FROM rooms WHERE id=?", (rid,))
            rr = cur.fetchone()
            if rr:
                rname, rmode, rdur, rstatus = rr[0], rr[1], rr[2], rr[3]
                # skip invitations for closed rooms
                if rstatus == 'closed':
                    invites_to_delete.append(iid)
                    continue
            else:
                # room doesn't exist anymore, delete invitation
                invites_to_delete.append(iid)
                continue
            # fetch sender's name
            cur.execute("SELECT name FROM users WHERE id=?", (frm,))
            ur = cur.fetchone()
            from_name = ur[0] if ur else f"User#{frm}"
            out.append({'inviteId': iid, 'roomId': rid, 'roomName': rname, 'fromUserId': frm, 'fromUserName': from_name, 'mode': rmode, 'durationSec': rdur, 'ts': tts})
        
        # clean up invitations for closed/deleted rooms
        for iid in invites_to_delete:
            try:
                cur.execute("DELETE FROM invitations WHERE id=?", (iid,))
            except Exception:
                pass
        
        return {'type': 'LIST_INVITES_RESP', 'data': {'ok': True, 'result': out}}

    if t == 'DELETE_INVITE':
        # accept data: { inviteId } OR { roomId, toUserId }
        if d.get('inviteId'):
            cur.execute("DELETE FROM invitations WHERE id=?", (d.get('inviteId'),))
        else:
            cur.execute("DELETE FROM invitations WHERE roomId=? AND toUserId=?", (d.get('roomId'), d.get('toUserId')))
        return {'type': 'DELETE_INVITE_RESP', 'data': {'ok': True}}

    if t == 'ADD_MEMBER':
        cur.execute("INSERT INTO room_members(roomId,userId) VALUES(?,?)", (d['roomId'], d['userId']))
        return {'type': 'ADD_MEMBER_RESP', 'data': {'ok': True}}

    if t == 'UPDATE_ROOM_STATUS':
        cur.execute("UPDATE rooms SET status=? WHERE id=?", (d['status'], d['roomId']))
        return {'type': 'UPDATE_ROOM_STATUS_RESP', 'data': {'ok': True}}

    if t == 'DELETE_ROOM':
        # remove membership rows then the room itself
        cur.execute("DELETE FROM room_members WHERE roomId=?", (d.get('roomId'),))
        cur.execute("DELETE FROM rooms WHERE id=?", (d.get('roomId'),))
        return {'type': 'DELETE_ROOM_RESP', 'data': {'ok': True}}

    # -------- GAME LOGS --------
    if t == 'ADD_GAMELOG':
        cur.execute("""INSERT INTO gamelogs(roomId,winnerId,loserId,finishedAt,duration,mode)
                       VALUES(?,?,?,?,?,?)""",
                    (d['roomId'], d.get('winnerId'), d.get('loserId'), ts(), d.get('duration',0), d.get('mode','timed')))
        gid = cur.lastrowid
        print(f"[DB] ADD_GAMELOG: created gamelog id={gid}")
        # if per-player results provided, insert into gamelog_players
        results = d.get('results')
        print(f"[DB] Processing results: {results}")
        if results and isinstance(results, list):
            for r in results:
                try:
                    uid = r.get('userId')
                    score = int(r.get('score', 0))
                    lines = int(r.get('lines', 0))
                    print(f"[DB] Processing player: uid={uid}, score={score}, lines={lines}")
                    cur.execute("INSERT INTO gamelog_players(gamelogId,userId,score,lines) VALUES(?,?,?,?)",
                                (gid, uid, score, lines))
                    print(f"[DB] Inserted into gamelog_players")
                    # accumulate into users.totalScore / totalLines if columns exist
                    try:
                        cur.execute("UPDATE users SET totalScore = COALESCE(totalScore,0) + ?, totalLines = COALESCE(totalLines,0) + ? WHERE id=?",
                                    (score, lines, uid))
                        print(f"[DB] ✅ Updated user {uid}: +{score} score, +{lines} lines")
                    except Exception as e:
                        print(f"[DB] ❌ Failed to update user {uid}: {e}")
                except Exception as e:
                    print(f"[DB] ❌ Failed to process result {r}: {e}")
        else:
            print(f"[DB] No results to process or invalid format")
        return {'type': 'ADD_GAMELOG_RESP', 'data': {'ok': True, 'id': gid}}

    if t == 'LIST_GAMELOGS':
        cur.execute("SELECT * FROM gamelogs ORDER BY id DESC LIMIT 20")
        logs = []
        for r in cur.fetchall():
            row = dict(zip([c[0] for c in cur.description], r))
            gid = row.get('id')
            # fetch players
            cur.execute("SELECT userId,score,lines FROM gamelog_players WHERE gamelogId=?", (gid,))
            players = [{'userId': p[0], 'score': p[1], 'lines': p[2]} for p in cur.fetchall()]
            row['players'] = players
            logs.append(row)
        return {'type': 'LIST_GAMELOGS_RESP', 'data': {'ok': True, 'result': logs}}

    return {'type': 'ERROR', 'data': {'ok': False, 'error': f'unknown type {t}'}}

# ------------------ Thread loop ------------------
def handle_client(conn, addr):
    # print("[DB] Client connected:", addr)  # 註解掉以減少日誌
    db = sqlite3.connect(DBPATH, check_same_thread=False)
    cur = db.cursor()
    try:
        while True:
            try:
                req = recv_msg(conn)
            except Exception:
                break
            resp = handle_cmd(cur, req)
            db.commit()
            try:
                send_msg(conn, resp)
            except Exception:
                break
    except Exception as e:
        print("[DB] Client error:", e)
    finally:
        conn.close()
        db.close()
        # print("[DB] Disconnected:", addr)  # 註解掉以減少日誌

def main():
    init_db()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT)); s.listen(10)
    print(f"[DB] Listening on {HOST}:{PORT}")
    while True:
        c, a = s.accept()
        threading.Thread(target=handle_client, args=(c, a), daemon=True).start()

if __name__ == '__main__':
    main()
