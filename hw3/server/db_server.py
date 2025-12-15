"""
Database Server for Game Store System
Handles persistent data storage using JSON files
"""

import json
import os
import threading
import hashlib
from datetime import datetime


class DatabaseServer:
    """Database server for storing all persistent data"""
    
    @staticmethod
    def _hash_password(password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        # Data files
        self.dev_users_file = os.path.join(data_dir, "dev_users.json")
        self.player_users_file = os.path.join(data_dir, "player_users.json")
        self.games_file = os.path.join(data_dir, "games.json")
        self.reviews_file = os.path.join(data_dir, "reviews.json")
        self.rooms_file = os.path.join(data_dir, "rooms.json")
        
        # Thread locks for concurrent access
        self.lock = threading.Lock()
        
        # Initialize data structures
        self.dev_users = self._load_json(self.dev_users_file, {})
        self.player_users = self._load_json(self.player_users_file, {})
        self.games = self._load_json(self.games_file, {})
        self.reviews = self._load_json(self.reviews_file, {})
        self.rooms = self._load_json(self.rooms_file, {})
        
        # Track online sessions
        self.dev_sessions = {}  # username -> connection
        self.player_sessions = {}  # username -> connection
    
    def _load_json(self, filepath, default):
        """Load JSON file or return default if not exists"""
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return default
        return default
    
    def _save_json(self, filepath, data):
        """Save data to JSON file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    # Developer User Management
    def register_dev_user(self, username, password):
        """Register a new developer user"""
        with self.lock:
            if username in self.dev_users:
                return False, "帳號已被使用"
            
            self.dev_users[username] = {
                "password": self._hash_password(password),
                "created_at": datetime.now().isoformat()
            }
            self._save_json(self.dev_users_file, self.dev_users)
            return True, "註冊成功"
    
    def login_dev_user(self, username, password):
        """Login developer user"""
        with self.lock:
            if username not in self.dev_users:
                return False, "帳號或密碼錯誤"
            
            if self.dev_users[username]["password"] != self._hash_password(password):
                return False, "帳號或密碼錯誤"
            
            if username in self.dev_sessions:
                return False, "帳號已在其他裝置登入"
            
            return True, "登入成功"
    
    def set_dev_session(self, username, conn=None):
        """Set developer session"""
        with self.lock:
            if conn:
                self.dev_sessions[username] = conn
            elif username in self.dev_sessions:
                del self.dev_sessions[username]
    
    # Player User Management
    def register_player_user(self, username, password):
        """Register a new player user"""
        with self.lock:
            if username in self.player_users:
                return False, "帳號已被使用"
            
            self.player_users[username] = {
                "password": self._hash_password(password),
                "created_at": datetime.now().isoformat(),
                "played_games": []
            }
            self._save_json(self.player_users_file, self.player_users)
            return True, "註冊成功"
    
    def login_player_user(self, username, password):
        """Login player user"""
        with self.lock:
            if username not in self.player_users:
                return False, "帳號或密碼錯誤"
            
            if self.player_users[username]["password"] != self._hash_password(password):
                return False, "帳號或密碼錯誤"
            
            if username in self.player_sessions:
                return False, "帳號已在其他裝置登入"
            
            return True, "登入成功"
    
    def set_player_session(self, username, conn=None):
        """Set player session"""
        with self.lock:
            if conn:
                self.player_sessions[username] = conn
            elif username in self.player_sessions:
                del self.player_sessions[username]
    
    # Game Management
    def add_game(self, game_id, game_data):
        """Add a new game"""
        with self.lock:
            self.games[game_id] = game_data
            self._save_json(self.games_file, self.games)
            return True
    
    def update_game(self, game_id, game_data):
        """Update an existing game"""
        with self.lock:
            if game_id not in self.games:
                return False, "遊戲不存在"
            
            # Keep original data and update
            self.games[game_id].update(game_data)
            self._save_json(self.games_file, self.games)
            return True, "更新成功"
    
    def delete_game(self, game_id):
        """Delete a game"""
        with self.lock:
            if game_id not in self.games:
                return False, "遊戲不存在"
            
            del self.games[game_id]
            self._save_json(self.games_file, self.games)
            return True, "刪除成功"
    
    def get_game(self, game_id):
        """Get game info (reload from file to ensure freshness)"""
        with self.lock:
            # Reload from file to get latest updates from other server instances
            self.games = self._load_json(self.games_file, {})
            return self.games.get(game_id)
    
    def get_all_games(self):
        """Get all games (reload from file to ensure freshness)"""
        with self.lock:
            # Reload from file to get latest updates from other server instances
            self.games = self._load_json(self.games_file, {})
            return dict(self.games)
    
    def get_games_by_author(self, author):
        """Get games by author (reload from file to ensure freshness)"""
        with self.lock:
            # Reload from file to get latest updates from other server instances
            self.games = self._load_json(self.games_file, {})
            return {gid: g for gid, g in self.games.items() if g.get('author') == author}
    
    # Review Management
    def add_review(self, game_id, username, rating, comment):
        """Add a review for a game"""
        with self.lock:
            if game_id not in self.reviews:
                self.reviews[game_id] = []
            
            review = {
                "username": username,
                "rating": rating,
                "comment": comment,
                "created_at": datetime.now().isoformat()
            }
            self.reviews[game_id].append(review)
            self._save_json(self.reviews_file, self.reviews)
            return True
    
    def get_reviews(self, game_id):
        """Get all reviews for a game"""
        with self.lock:
            return self.reviews.get(game_id, [])
    
    def get_average_rating(self, game_id):
        """Get average rating for a game"""
        with self.lock:
            reviews = self.reviews.get(game_id, [])
            if not reviews:
                return 0
            return sum(r['rating'] for r in reviews) / len(reviews)
    
    # Room Management
    def create_room(self, room_id, room_data):
        """Create a new room"""
        with self.lock:
            self.rooms[room_id] = room_data
            self._save_json(self.rooms_file, self.rooms)
            return True
    
    def get_room(self, room_id):
        """Get room info"""
        with self.lock:
            return self.rooms.get(room_id)
    
    def get_all_rooms(self):
        """Get all rooms"""
        with self.lock:
            return dict(self.rooms)
    
    def update_room(self, room_id, room_data):
        """Update room info"""
        with self.lock:
            if room_id not in self.rooms:
                return False
            self.rooms[room_id].update(room_data)
            self._save_json(self.rooms_file, self.rooms)
            return True
    
    def delete_room(self, room_id):
        """Delete a room"""
        with self.lock:
            if room_id in self.rooms:
                del self.rooms[room_id]
                self._save_json(self.rooms_file, self.rooms)
                return True
            return False
    
    def add_played_game(self, username, game_id):
        """Mark that a player has played a game"""
        with self.lock:
            if username in self.player_users:
                if 'played_games' not in self.player_users[username]:
                    self.player_users[username]['played_games'] = []
                if game_id not in self.player_users[username]['played_games']:
                    self.player_users[username]['played_games'].append(game_id)
                    self._save_json(self.player_users_file, self.player_users)
    
    def has_played_game(self, username, game_id):
        """Check if player has played a game"""
        with self.lock:
            # Reload from file to get latest data
            self.player_users = self._load_json(self.player_users_file, {})
            if username in self.player_users:
                return game_id in self.player_users[username].get('played_games', [])
            return False


# Singleton instance
_db_instance = None

def get_db():
    """Get database singleton instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseServer()
    return _db_instance
