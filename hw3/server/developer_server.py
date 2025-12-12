"""
Developer Server
Handles developer operations: upload, update, delete games
"""

import socket
import threading
import os
import shutil
import json
from protocol import Protocol, MessageType, recv_message, send_message, recv_file
from db_server import get_db


class DeveloperServer:
    def __init__(self, host='0.0.0.0', port=8001, upload_dir='uploaded_games'):
        self.host = host
        self.port = port
        self.upload_dir = upload_dir
        self.db = get_db()
        self.server_socket = None
        self.running = False
        
        os.makedirs(upload_dir, exist_ok=True)
    
    def start(self):
        """Start the developer server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True
        
        print(f"Developer Server started on {self.host}:{self.port}")
        
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                print(f"Developer client connected from {address}")
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
        """Handle developer client connection"""
        username = None
        
        try:
            while True:
                result = recv_message(client_socket)
                if not result:
                    break
                
                msg_type, data = result
                
                if msg_type == MessageType.DEV_REGISTER:
                    response = self.handle_register(data)
                    client_socket.sendall(response)
                
                elif msg_type == MessageType.DEV_LOGIN:
                    response, user = self.handle_login(data)
                    client_socket.sendall(response)
                    if user:
                        username = user
                        self.db.set_dev_session(username, client_socket)
                
                elif msg_type == MessageType.DEV_LOGOUT:
                    if username:
                        self.db.set_dev_session(username, None)
                        username = None
                    client_socket.sendall(Protocol.success_response({"message": "登出成功"}))
                
                elif msg_type == MessageType.DEV_UPLOAD_GAME:
                    if not username:
                        client_socket.sendall(Protocol.error_response("請先登入"))
                        continue
                    response = self.handle_upload_game(data, username, client_socket)
                    client_socket.sendall(response)
                
                elif msg_type == MessageType.DEV_UPDATE_GAME:
                    if not username:
                        client_socket.sendall(Protocol.error_response("請先登入"))
                        continue
                    response = self.handle_update_game(data, username, client_socket)
                    client_socket.sendall(response)
                
                elif msg_type == MessageType.DEV_DELETE_GAME:
                    if not username:
                        client_socket.sendall(Protocol.error_response("請先登入"))
                        continue
                    response = self.handle_delete_game(data, username)
                    client_socket.sendall(response)
                
                elif msg_type == MessageType.DEV_LIST_MY_GAMES:
                    if not username:
                        client_socket.sendall(Protocol.error_response("請先登入"))
                        continue
                    response = self.handle_list_my_games(username)
                    client_socket.sendall(response)
                
                else:
                    client_socket.sendall(Protocol.error_response("未知的請求類型"))
        
        except Exception as e:
            print(f"Error handling client {address}: {e}")
        
        finally:
            if username:
                self.db.set_dev_session(username, None)
            client_socket.close()
            print(f"Developer client {address} disconnected")
    
    def handle_register(self, data):
        """Handle developer registration"""
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return Protocol.error_response("用戶名和密碼不能為空")
        
        success, message = self.db.register_dev_user(username, password)
        
        if success:
            return Protocol.success_response({"message": message})
        else:
            return Protocol.error_response(message)
    
    def handle_login(self, data):
        """Handle developer login"""
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return Protocol.error_response("用戶名和密碼不能為空"), None
        
        success, message = self.db.login_dev_user(username, password)
        
        if success:
            return Protocol.success_response({"message": message, "username": username}), username
        else:
            return Protocol.error_response(message), None
    
    def handle_upload_game(self, data, username, client_socket):
        """Handle game upload"""
        try:
            game_name = data.get('game_name')
            description = data.get('description')
            game_type = data.get('game_type')  # CLI, GUI, MULTIPLAYER
            max_players = data.get('max_players', 2)
            version = data.get('version', '1.0.0')
            start_command = data.get('start_command')
            
            if not all([game_name, description, game_type, start_command]):
                return Protocol.error_response("缺少必要欄位")
            
            # Generate game ID
            game_id = f"{username}_{game_name}".replace(' ', '_')
            
            # Check if game already exists
            if self.db.get_game(game_id):
                return Protocol.error_response("遊戲名稱已存在，請使用更新功能")
            
            # Send ready signal
            send_message(client_socket, MessageType.SUCCESS, {"message": "準備接收遊戲檔案"})
            
            # Receive game files as a zip
            game_dir = os.path.join(self.upload_dir, game_id, version)
            os.makedirs(game_dir, exist_ok=True)
            
            zip_path = os.path.join(game_dir, "game.zip")
            if not recv_file(client_socket, zip_path):
                return Protocol.error_response("接收遊戲檔案失敗")
            
            # Extract zip file
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(game_dir)
            os.remove(zip_path)
            
            # Save game metadata
            game_data = {
                "game_id": game_id,
                "name": game_name,
                "author": username,
                "description": description,
                "type": game_type,
                "max_players": max_players,
                "version": version,
                "start_command": start_command,
                "created_at": __import__('datetime').datetime.now().isoformat(),
                "updated_at": __import__('datetime').datetime.now().isoformat(),
                "active": True
            }
            
            self.db.add_game(game_id, game_data)
            
            return Protocol.success_response({
                "message": "遊戲上架成功",
                "game_id": game_id
            })
        
        except Exception as e:
            return Protocol.error_response(f"上架失敗: {str(e)}")
    
    def handle_update_game(self, data, username, client_socket):
        """Handle game update"""
        try:
            game_id = data.get('game_id')
            new_version = data.get('version')
            update_notes = data.get('update_notes', '')
            
            # 錯誤處理：缺少必要資訊
            if not game_id or not new_version:
                return Protocol.error_response("缺少遊戲ID或版本號")
            
            # 驗證版本號格式
            if not new_version.replace('.', '').replace('-', '').replace('_', '').isalnum():
                return Protocol.error_response("版本號格式不合法")
            
            # Check if game exists and belongs to user
            game = self.db.get_game(game_id)
            
            # 錯誤處理：遊戲不存在
            if not game:
                return Protocol.error_response("遊戲不存在")
            
            # 錯誤處理：無權限更新此遊戲
            if game['author'] != username:
                return Protocol.error_response("無權限更新此遊戲")
            
            # 檢查遊戲是否已下架
            if not game.get('active', True):
                return Protocol.error_response("無法更新已下架的遊戲")
            
            # Send ready signal
            send_message(client_socket, MessageType.SUCCESS, {"message": "準備接收遊戲檔案"})
            
            # Receive new game files
            game_dir = os.path.join(self.upload_dir, game_id, new_version)
            os.makedirs(game_dir, exist_ok=True)
            
            zip_path = os.path.join(game_dir, "game.zip")
            
            # 錯誤處理：接收檔案失敗
            if not recv_file(client_socket, zip_path):
                # 清理失敗的目錄
                import shutil
                if os.path.exists(game_dir):
                    shutil.rmtree(game_dir)
                return Protocol.error_response("接收遊戲檔案失敗")
            
            # Extract zip file
            try:
                import zipfile
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(game_dir)
                os.remove(zip_path)
            except Exception as e:
                # 清理失敗的目錄
                import shutil
                if os.path.exists(game_dir):
                    shutil.rmtree(game_dir)
                return Protocol.error_response(f"解壓縮遊戲檔案失敗: {str(e)}")
            
            # Update game metadata
            update_data = {
                "version": new_version,
                "updated_at": __import__('datetime').datetime.now().isoformat()
            }
            
            # 儲存更新說明
            if update_notes:
                # 可以在這裡將更新說明存到遊戲的 update_history 或單獨的文件
                update_data['last_update_notes'] = update_notes
            
            # Update other fields if provided
            for field in ['description', 'start_command', 'max_players']:
                if field in data:
                    update_data[field] = data[field]
            
            success, message = self.db.update_game(game_id, update_data)
            
            if not success:
                return Protocol.error_response(message)
            
            return Protocol.success_response({
                "message": f"遊戲已成功更新至版本 {new_version}",
                "game_id": game_id,
                "version": new_version,
                "game_name": game['name']
            })
        
        except Exception as e:
            # 錯誤處理：伺服器端異常
            print(f"Update game error: {e}")
            import traceback
            traceback.print_exc()
            return Protocol.error_response(f"伺服器錯誤：{str(e)}")
    
    def handle_delete_game(self, data, username):
        """Handle game deletion"""
        game_id = data.get('game_id')
        
        if not game_id:
            return Protocol.error_response("缺少遊戲ID")
        
        # Check if game exists and belongs to user
        game = self.db.get_game(game_id)
        if not game:
            return Protocol.error_response("遊戲不存在")
        
        if game['author'] != username:
            return Protocol.error_response("無權限下架此遊戲")
        
        # Mark game as inactive instead of deleting
        self.db.update_game(game_id, {"active": False})
        
        return Protocol.success_response({"message": "遊戲已下架"})
    
    def handle_list_my_games(self, username):
        """List games by this developer"""
        games = self.db.get_games_by_author(username)
        
        game_list = []
        for game_id, game in games.items():
            game_list.append({
                "game_id": game_id,
                "name": game['name'],
                "version": game['version'],
                "type": game['type'],
                "active": game.get('active', True),
                "created_at": game.get('created_at', ''),
                "updated_at": game.get('updated_at', game.get('created_at', ''))
            })
        
        return Protocol.success_response({"games": game_list})
    
    def stop(self):
        """Stop the server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()


if __name__ == "__main__":
    server = DeveloperServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nShutting down Developer Server...")
        server.stop()
