"""
Communication Protocol for Game Store System
Defines message types and data structures for client-server communication
"""

import json
from enum import Enum

class MessageType(Enum):
    # Developer Messages
    DEV_REGISTER = "dev_register"
    DEV_LOGIN = "dev_login"
    DEV_LOGOUT = "dev_logout"
    DEV_UPLOAD_GAME = "dev_upload_game"
    DEV_UPDATE_GAME = "dev_update_game"
    DEV_DELETE_GAME = "dev_delete_game"
    DEV_LIST_MY_GAMES = "dev_list_my_games"
    
    # Player Messages
    PLAYER_REGISTER = "player_register"
    PLAYER_LOGIN = "player_login"
    PLAYER_LIST_GAMES = "player_list_games"
    PLAYER_GAME_DETAILS = "player_game_details"
    PLAYER_DOWNLOAD_GAME = "player_download_game"
    PLAYER_CREATE_ROOM = "player_create_room"
    PLAYER_JOIN_ROOM = "player_join_room"
    PLAYER_LEAVE_ROOM = "player_leave_room"
    PLAYER_LIST_ROOMS = "player_list_rooms"
    PLAYER_START_GAME = "player_start_game"
    PLAYER_RATE_GAME = "player_rate_game"
    PLAYER_REVIEW_GAME = "player_review_game"
    PLAYER_LIST_REVIEWS = "player_list_reviews"
    
    # Server Responses
    SUCCESS = "success"
    ERROR = "error"
    
    # Notifications
    ROOM_UPDATE = "room_update"
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"
    GAME_STARTED = "game_started"


class Protocol:
    """Protocol handler for encoding/decoding messages"""
    
    @staticmethod
    def encode_message(msg_type: MessageType, data: dict) -> bytes:
        """Encode a message to bytes"""
        message = {
            "type": msg_type.value,
            "data": data
        }
        json_str = json.dumps(message)
        # Add length prefix (4 bytes)
        length = len(json_str.encode('utf-8'))
        return length.to_bytes(4, byteorder='big') + json_str.encode('utf-8')
    
    @staticmethod
    def decode_message(data: bytes) -> tuple:
        """Decode a message from bytes. Returns (msg_type, data)"""
        try:
            message = json.loads(data.decode('utf-8'))
            msg_type = MessageType(message['type'])
            return msg_type, message['data']
        except Exception as e:
            raise ValueError(f"Failed to decode message: {e}")
    
    @staticmethod
    def success_response(data: dict = None) -> bytes:
        """Create a success response"""
        return Protocol.encode_message(MessageType.SUCCESS, data or {})
    
    @staticmethod
    def error_response(error_msg: str) -> bytes:
        """Create an error response"""
        return Protocol.encode_message(MessageType.ERROR, {"error": error_msg})


def recv_message(sock):
    """Receive a complete message from socket"""
    # First, receive the length prefix (4 bytes)
    length_bytes = recv_exact(sock, 4)
    if not length_bytes:
        return None
    
    length = int.from_bytes(length_bytes, byteorder='big')
    
    # Then receive the actual message
    data = recv_exact(sock, length)
    if not data:
        return None
    
    return Protocol.decode_message(data)


def send_message(sock, msg_type: MessageType, data: dict):
    """Send a message through socket"""
    message = Protocol.encode_message(msg_type, data)
    sock.sendall(message)


def recv_exact(sock, n):
    """Receive exactly n bytes from socket"""
    data = b''
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def send_file(sock, file_path):
    """Send a file through socket"""
    import os
    
    # Send file size first
    file_size = os.path.getsize(file_path)
    sock.sendall(file_size.to_bytes(8, byteorder='big'))
    
    # Send file data
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(4096)
            if not chunk:
                break
            sock.sendall(chunk)


def recv_file(sock, save_path):
    """Receive a file from socket"""
    import os
    
    # Receive file size first
    size_bytes = recv_exact(sock, 8)
    if not size_bytes:
        return False
    
    file_size = int.from_bytes(size_bytes, byteorder='big')
    
    # Create directory if not exists
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    # Receive file data
    received = 0
    with open(save_path, 'wb') as f:
        while received < file_size:
            chunk_size = min(4096, file_size - received)
            chunk = recv_exact(sock, chunk_size)
            if not chunk:
                return False
            f.write(chunk)
            received += len(chunk)
    
    return True
