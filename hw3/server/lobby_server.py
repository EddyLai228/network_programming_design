"""
Lobby Server
Handles player operations: browse games, create/join rooms, download games
"""

import socket
import threading
import os
import shutil
import zipfile
from protocol import Protocol, MessageType, recv_message, send_message, send_file
from db_server import get_db


class LobbyServer:
    def __init__(self, host='0.0.0.0', port=8002, upload_dir='uploaded_games'):
        self.host = host
        self.port = port
        self.upload_dir = upload_dir
        self.db = get_db()
        self.server_socket = None
        self.running = False
        
        # Track active game servers
        self.game_servers = {}  # room_id -> process
        
        # Clear all rooms on server startup (all players disconnected)
        self._clear_all_rooms()
    
    def _clear_all_rooms(self):
        """Clear all rooms when server starts (all players have disconnected)"""
        rooms = self.db.get_all_rooms()
        for room_id in list(rooms.keys()):
            self.db.delete_room(room_id)
        print("All rooms cleared on server startup")
    
    def start(self):
        """Start the lobby server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True
        
        print(f"Lobby Server started on {self.host}:{self.port}")
        
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                print(f"Player client connected from {address}")
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address)
                )
                client_thread.daemon = True
                client_thread.start()
            except Exception as e:
                if self.running:
                    print(f"Error accepting connection: {e}")
    
    def handle_client(self, client_socket, address):
        """Handle player client connection"""
        username = None
        
        try:
            while True:
                result = recv_message(client_socket)
                if not result:
                    break
                
                msg_type, data = result
                
                if msg_type == MessageType.PLAYER_REGISTER:
                    response = self.handle_register(data)
                    client_socket.sendall(response)
                
                elif msg_type == MessageType.PLAYER_LOGIN:
                    response, user = self.handle_login(data)
                    client_socket.sendall(response)
                    if user:
                        username = user
                        self.db.set_player_session(username, client_socket)
                
                elif msg_type == MessageType.PLAYER_LOGOUT:
                    if username:
                        self.db.set_player_session(username, None)
                        username = None
                    client_socket.sendall(Protocol.success_response({"message": "登出成功"}))
                
                elif msg_type == MessageType.PLAYER_LIST_GAMES:
                    response = self.handle_list_games()
                    client_socket.sendall(response)
                
                elif msg_type == MessageType.PLAYER_GAME_DETAILS:
                    response = self.handle_game_details(data)
                    client_socket.sendall(response)
                
                elif msg_type == MessageType.PLAYER_DOWNLOAD_GAME:
                    if not username:
                        client_socket.sendall(Protocol.error_response("請先登入"))
                        continue
                    response = self.handle_download_game(data, username, client_socket)
                    client_socket.sendall(response)
                
                elif msg_type == MessageType.PLAYER_CREATE_ROOM:
                    if not username:
                        client_socket.sendall(Protocol.error_response("請先登入"))
                        continue
                    response = self.handle_create_room(data, username)
                    client_socket.sendall(response)
                
                elif msg_type == MessageType.PLAYER_LIST_ROOMS:
                    response = self.handle_list_rooms()
                    client_socket.sendall(response)
                
                elif msg_type == MessageType.PLAYER_JOIN_ROOM:
                    if not username:
                        client_socket.sendall(Protocol.error_response("請先登入"))
                        continue
                    response = self.handle_join_room(data, username)
                    client_socket.sendall(response)
                
                elif msg_type == MessageType.PLAYER_LEAVE_ROOM:
                    if not username:
                        client_socket.sendall(Protocol.error_response("請先登入"))
                        continue
                    response = self.handle_leave_room(data, username)
                    client_socket.sendall(response)
                
                elif msg_type == MessageType.PLAYER_START_GAME:
                    if not username:
                        client_socket.sendall(Protocol.error_response("請先登入"))
                        continue
                    response = self.handle_start_game(data, username)
                    client_socket.sendall(response)
                
                elif msg_type == MessageType.PLAYER_UPDATE_GAME_PORT:
                    if not username:
                        client_socket.sendall(Protocol.error_response("請先登入"))
                        continue
                    response = self.handle_update_game_port(data, username)
                    client_socket.sendall(response)
                
                elif msg_type == MessageType.PLAYER_END_GAME:
                    if not username:
                        client_socket.sendall(Protocol.error_response("請先登入"))
                        continue
                    response = self.handle_end_game(data, username)
                    client_socket.sendall(response)
                
                elif msg_type == MessageType.PLAYER_RATE_GAME:
                    if not username:
                        client_socket.sendall(Protocol.error_response("請先登入"))
                        continue
                    response = self.handle_rate_game(data, username)
                    client_socket.sendall(response)
                
                elif msg_type == MessageType.PLAYER_REVIEW_GAME:
                    if not username:
                        client_socket.sendall(Protocol.error_response("請先登入"))
                        continue
                    response = self.handle_review_game(data, username)
                    client_socket.sendall(response)
                
                elif msg_type == MessageType.PLAYER_LIST_REVIEWS:
                    response = self.handle_list_reviews(data)
                    client_socket.sendall(response)
                
                else:
                    client_socket.sendall(Protocol.error_response("未知的請求類型"))
        
        except Exception as e:
            print(f"Error handling client {address}: {e}")
        
        finally:
            if username:
                # Clear session
                self.db.set_player_session(username, None)
                
                # Remove player from any room they were in
                rooms = self.db.get_all_rooms()
                for room_id, room in rooms.items():
                    if username in room['players']:
                        print(f"Removing {username} from room {room_id} due to disconnection")
                        room['players'].remove(username)
                        
                        # If room is empty, delete it
                        if not room['players']:
                            self.db.delete_room(room_id)
                            print(f"Room {room_id} deleted (empty)")
                        else:
                            # If host disconnected, assign new host
                            if room['host'] == username:
                                room['host'] = room['players'][0]
                                print(f"New host for room {room_id}: {room['host']}")
                            self.db.update_room(room_id, room)
                        break
            
            client_socket.close()
            print(f"Player client {address} disconnected")
    
    def handle_register(self, data):
        """Handle player registration"""
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return Protocol.error_response("用戶名和密碼不能為空")
        
        success, message = self.db.register_player_user(username, password)
        
        if success:
            return Protocol.success_response({"message": message})
        else:
            return Protocol.error_response(message)
    
    def handle_login(self, data):
        """Handle player login"""
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return Protocol.error_response("用戶名和密碼不能為空"), None
        
        success, message = self.db.login_player_user(username, password)
        
        if success:
            return Protocol.success_response({"message": message, "username": username}), username
        else:
            return Protocol.error_response(message), None
    
    def handle_list_games(self):
        """List all active games"""
        all_games = self.db.get_all_games()
        
        game_list = []
        for game_id, game in all_games.items():
            if game.get('active', True):
                avg_rating = self.db.get_average_rating(game_id)
                game_list.append({
                    "game_id": game_id,
                    "name": game['name'],
                    "author": game['author'],
                    "type": game['type'],
                    "max_players": game['max_players'],
                    "version": game['version'],
                    "rating": round(avg_rating, 1)
                })
        
        return Protocol.success_response({"games": game_list})
    
    def handle_game_details(self, data):
        """Get detailed game information"""
        game_id = data.get('game_id')
        
        if not game_id:
            return Protocol.error_response("缺少遊戲ID")
        
        game = self.db.get_game(game_id)
        if not game or not game.get('active', True):
            return Protocol.error_response("遊戲不存在")
        
        avg_rating = self.db.get_average_rating(game_id)
        reviews = self.db.get_reviews(game_id)
        
        game_info = {
            "game_id": game_id,
            "name": game['name'],
            "author": game['author'],
            "description": game['description'],
            "type": game['type'],
            "max_players": game['max_players'],
            "version": game['version'],
            "created_at": game['created_at'],
            "updated_at": game['updated_at'],
            "rating": round(avg_rating, 1),
            "review_count": len(reviews)
        }
        
        return Protocol.success_response({"game": game_info})
    
    def handle_download_game(self, data, username, client_socket):
        """Handle game download"""
        try:
            game_id = data.get('game_id')
            
            if not game_id:
                return Protocol.error_response("缺少遊戲ID")
            
            game = self.db.get_game(game_id)
            if not game or not game.get('active', True):
                return Protocol.error_response("遊戲不存在或已下架")
            
            version = game['version']
            game_dir = os.path.join(self.upload_dir, game_id, version)
            
            if not os.path.exists(game_dir):
                return Protocol.error_response("遊戲檔案不存在")
            
            # Create zip file for download
            temp_zip = f"/tmp/{game_id}_{version}.zip"
            with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(game_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, game_dir)
                        zipf.write(file_path, arcname)
            
            # Send game info first
            send_message(client_socket, MessageType.SUCCESS, {
                "game_id": game_id,
                "version": version,
                "start_command": game['start_command']
            })
            
            # Send zip file
            send_file(client_socket, temp_zip)
            
            # Clean up
            os.remove(temp_zip)
            
            return Protocol.success_response({"message": "遊戲下載完成"})
        
        except Exception as e:
            return Protocol.error_response(f"下載失敗: {str(e)}")
    
    def handle_create_room(self, data, username):
        """Handle room creation"""
        try:
            game_id = data.get('game_id')
            room_name = data.get('room_name', f"{username}的房間")
            
            if not game_id:
                return Protocol.error_response("缺少遊戲ID")
            
            game = self.db.get_game(game_id)
            if not game:
                return Protocol.error_response("遊戲不存在")
            
            # Allow creating rooms for downloaded games even if inactive
            # This allows players who downloaded a game to continue playing after it's delisted
            
            # Generate room ID
            import uuid
            room_id = str(uuid.uuid4())[:8]
            
            room_data = {
                "room_id": room_id,
                "room_name": room_name,
                "game_id": game_id,
                "game_name": game['name'],
                "game_version": game['version'],  # Store game version
                "host": username,
                "players": [],  # Creator must explicitly join
                "max_players": game['max_players'],
                "status": "waiting",  # waiting, playing, finished
                "created_at": __import__('datetime').datetime.now().isoformat()
            }
            
            self.db.create_room(room_id, room_data)
            
            return Protocol.success_response({
                "message": "房間建立成功",
                "room_id": room_id,
                "room_data": room_data
            })
        
        except Exception as e:
            return Protocol.error_response(f"建立房間失敗: {str(e)}")
    
    def handle_list_rooms(self):
        """List all active rooms"""
        rooms = self.db.get_all_rooms()
        
        room_list = []
        for room_id, room in rooms.items():
            if room['status'] != 'finished':
                room_list.append({
                    "room_id": room_id,
                    "room_name": room['room_name'],
                    "game_id": room['game_id'],  # Include game_id for start_game()
                    "game_name": room['game_name'],
                    "game_version": room.get('game_version', '1.0.0'),  # Include game version
                    "game_port": room.get('game_port'),  # Include game server port if available
                    "host": room['host'],
                    "players": room['players'],  # Return player list instead of count
                    "max_players": room['max_players'],
                    "status": room['status']
                })
        
        return Protocol.success_response({"rooms": room_list})
    
    def handle_join_room(self, data, username):
        """Handle joining a room"""
        room_id = data.get('room_id')
        player_game_version = data.get('game_version')  # Get player's local game version
        
        if not room_id:
            return Protocol.error_response("缺少房間ID")
        
        # Check if player is already in another room
        all_rooms = self.db.get_all_rooms()
        for rid, r in all_rooms.items():
            if username in r['players'] and rid != room_id:
                return Protocol.error_response(f"你已經在房間中: {r['room_name']}，請先離開再加入其他房間")
        
        room = self.db.get_room(room_id)
        if not room:
            return Protocol.error_response("房間不存在")
        
        # Check game version match
        if player_game_version != room['game_version']:
            return Protocol.error_response(
                f"遊戲版本不符！房間版本: {room['game_version']}，你的版本: {player_game_version or '未安裝'}。\n請更新或下載正確版本的遊戲。"
            )
        
        if room['status'] != 'waiting':
            return Protocol.error_response("房間已開始遊戲")
        
        if len(room['players']) >= room['max_players']:
            return Protocol.error_response("房間已滿")
        
        if username in room['players']:
            return Protocol.error_response("你已在房間中")
        
        room['players'].append(username)
        self.db.update_room(room_id, room)
        
        return Protocol.success_response({
            "message": "加入房間成功",
            "room_data": room
        })
    
    def handle_leave_room(self, data, username):
        """Handle leaving a room"""
        room_id = data.get('room_id')
        
        if not room_id:
            return Protocol.error_response("缺少房間ID")
        
        room = self.db.get_room(room_id)
        if not room:
            return Protocol.error_response("房間不存在")
        
        if username not in room['players']:
            return Protocol.error_response("你不在此房間中")
        
        room['players'].remove(username)
        
        # If room is empty, delete it
        if not room['players']:
            self.db.delete_room(room_id)
        else:
            # If host leaves, assign new host
            if room['host'] == username:
                room['host'] = room['players'][0]
            self.db.update_room(room_id, room)
        
        return Protocol.success_response({"message": "離開房間成功"})
    
    def handle_start_game(self, data, username):
        """Handle starting a game (host only)"""
        room_id = data.get('room_id')
        
        if not room_id:
            return Protocol.error_response("缺少房間ID")
        
        room = self.db.get_room(room_id)
        if not room:
            return Protocol.error_response("房間不存在")
        
        # Check if user is the host
        if room['host'] != username:
            return Protocol.error_response("只有房主可以開始遊戲")
        
        # Check if user is in the room
        if username not in room['players']:
            return Protocol.error_response("你不在此房間中")
        
        # Check if enough players
        current_players = len(room['players'])
        if current_players < room['max_players']:
            return Protocol.error_response(f"房間人數不足 ({current_players}/{room['max_players']})")
        
        # Update room status to playing
        room['status'] = 'playing'
        self.db.update_room(room_id, room)
        
        return Protocol.success_response({
            "message": "遊戲已開始，已通知所有玩家",
            "room_data": room
        })
    
    def handle_update_game_port(self, data, username):
        """Handle updating game server port (host only)"""
        room_id = data.get('room_id')
        game_port = data.get('game_port')
        
        if not room_id or not game_port:
            return Protocol.error_response("缺少房間ID或遊戲端口")
        
        room = self.db.get_room(room_id)
        if not room:
            return Protocol.error_response("房間不存在")
        
        # Check if user is the host
        if room['host'] != username:
            return Protocol.error_response("只有房主可以更新遊戲端口")
        
        # Update room with game port
        room['game_port'] = game_port
        self.db.update_room(room_id, room)
        
        return Protocol.success_response({
            "message": f"遊戲端口已更新: {game_port}",
            "room_data": room
        })
    
    def handle_end_game(self, data, username):
        """Handle ending a game and resetting room status (host only)"""
        room_id = data.get('room_id')
        game_result = data.get('result', '')
        
        if not room_id:
            return Protocol.error_response("缺少房間ID")
        
        room = self.db.get_room(room_id)
        if not room:
            return Protocol.error_response("房間不存在")
        
        # Check if user is the host
        if room['host'] != username:
            return Protocol.error_response("只有房主可以結束遊戲")
        
        # Reset room status to waiting
        room['status'] = 'waiting'
        room['game_port'] = None  # Clear game port
        room['game_result'] = game_result  # Store game result
        self.db.update_room(room_id, room)
        
        return Protocol.success_response({
            "message": "遊戲已結束，房間重置為等待狀態",
            "result": game_result,
            "room_data": room
        })
    
    def handle_rate_game(self, data, username):
        """Handle game rating"""
        game_id = data.get('game_id')
        rating = data.get('rating')
        
        if not game_id or rating is None:
            return Protocol.error_response("缺少遊戲ID或評分")
        
        if not isinstance(rating, (int, float)) or rating < 1 or rating > 5:
            return Protocol.error_response("評分必須在1-5之間")
        
        # Check if player has played this game
        if not self.db.has_played_game(username, game_id):
            return Protocol.error_response("你尚未遊玩此遊戲")
        
        self.db.add_review(game_id, username, rating, "")
        
        return Protocol.success_response({"message": "評分成功"})
    
    def handle_review_game(self, data, username):
        """Handle game review"""
        game_id = data.get('game_id')
        rating = data.get('rating')
        comment = data.get('comment', '')
        
        if not game_id or rating is None:
            return Protocol.error_response("缺少遊戲ID或評分")
        
        if not isinstance(rating, (int, float)) or rating < 1 or rating > 5:
            return Protocol.error_response("評分必須在1-5之間")
        
        # Check if player has played this game
        if not self.db.has_played_game(username, game_id):
            return Protocol.error_response("你尚未遊玩此遊戲")
        
        self.db.add_review(game_id, username, rating, comment)
        
        return Protocol.success_response({"message": "評論成功"})
    
    def handle_list_reviews(self, data):
        """List reviews for a game"""
        game_id = data.get('game_id')
        
        if not game_id:
            return Protocol.error_response("缺少遊戲ID")
        
        reviews = self.db.get_reviews(game_id)
        
        return Protocol.success_response({"reviews": reviews})
    
    def stop(self):
        """Stop the server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()


if __name__ == "__main__":
    server = LobbyServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nShutting down Lobby Server...")
        server.stop()
