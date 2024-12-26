"""
Database storage module for MAIA.
Handles persistent storage of face encodings, commands, and user data.
"""
import sqlite3
import json
import numpy as np
from typing import Dict, List, Optional, Any
import asyncio
import logging
from datetime import datetime
import os

_LOGGER = logging.getLogger(__name__)

class BaseStorage:
    def __init__(self):
        self.db_dir = "database"
        self.db_path = os.path.join(self.db_dir, "maia.db")
        self.ensure_database()
        self.lock = asyncio.Lock()

    def ensure_database(self):
        """Ensure database and tables exist."""
        if not os.path.exists(self.db_dir):
            os.makedirs(self.db_dir)
            
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS face_encodings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    encoding BLOB NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    command TEXT NOT NULL,
                    response TEXT,
                    context TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL,
                    name TEXT,
                    preferences TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP
                )
            """)
            
            conn.commit()

class FaceStorage(BaseStorage):
    async def store_face_encoding(self, user_id: str,
                                encoding: np.ndarray,
                                metadata: Dict = None) -> bool:
        """
        Store a face encoding for a user.
        
        Args:
            user_id: User identifier
            encoding: Face encoding array
            metadata: Additional metadata
            
        Returns:
            bool indicating success
        """
        try:
            async with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Convert numpy array to bytes
                    encoding_bytes = encoding.tobytes()
                    
                    # Convert metadata to JSON
                    metadata_json = json.dumps(metadata) if metadata else None
                    
                    cursor.execute("""
                        INSERT INTO face_encodings (user_id, encoding, metadata)
                        VALUES (?, ?, ?)
                    """, (user_id, encoding_bytes, metadata_json))
                    
                    conn.commit()
                    
            return True
            
        except Exception as e:
            _LOGGER.error(f"Error storing face encoding: {str(e)}")
            return False

    async def get_face_encoding(self, user_id: str) -> Optional[np.ndarray]:
        """Get the latest face encoding for a user."""
        try:
            async with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        SELECT encoding FROM face_encodings
                        WHERE user_id = ?
                        ORDER BY created_at DESC
                        LIMIT 1
                    """, (user_id,))
                    
                    result = cursor.fetchone()
                    
                    if result:
                        # Convert bytes back to numpy array
                        encoding_bytes = result[0]
                        return np.frombuffer(encoding_bytes, dtype=np.float64)
                        
            return None
            
        except Exception as e:
            _LOGGER.error(f"Error getting face encoding: {str(e)}")
            return None

    async def get_all_face_encodings(self) -> Dict[str, np.ndarray]:
        """Get all stored face encodings."""
        try:
            async with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        SELECT user_id, encoding FROM (
                            SELECT user_id, encoding,
                                   ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) as rn
                            FROM face_encodings
                        ) tmp
                        WHERE rn = 1
                    """)
                    
                    results = cursor.fetchall()
                    
                    encodings = {}
                    for user_id, encoding_bytes in results:
                        encodings[user_id] = np.frombuffer(encoding_bytes, dtype=np.float64)
                        
                    return encodings
                    
        except Exception as e:
            _LOGGER.error(f"Error getting all face encodings: {str(e)}")
            return {}

class CommandStorage(BaseStorage):
    async def store_command(self, user_id: str, command: str,
                          response: Dict[str, Any],
                          context: Dict[str, Any] = None) -> bool:
        """
        Store a command and its response.
        
        Args:
            user_id: User identifier
            command: The command text
            response: Command response data
            context: Command context
            
        Returns:
            bool indicating success
        """
        try:
            async with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Convert dictionaries to JSON
                    response_json = json.dumps(response)
                    context_json = json.dumps(context) if context else None
                    
                    cursor.execute("""
                        INSERT INTO commands (user_id, command, response, context)
                        VALUES (?, ?, ?, ?)
                    """, (user_id, command, response_json, context_json))
                    
                    # Update user's last seen timestamp
                    cursor.execute("""
                        INSERT INTO users (user_id, last_seen)
                        VALUES (?, CURRENT_TIMESTAMP)
                        ON CONFLICT(user_id) DO UPDATE SET last_seen = CURRENT_TIMESTAMP
                    """, (user_id,))
                    
                    conn.commit()
                    
            return True
            
        except Exception as e:
            _LOGGER.error(f"Error storing command: {str(e)}")
            return False

    async def get_user_history(self, user_id: str,
                             limit: int = 10) -> List[Dict[str, Any]]:
        """Get command history for a user."""
        try:
            async with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        SELECT command, response, context, created_at
                        FROM commands
                        WHERE user_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (user_id, limit))
                    
                    results = cursor.fetchall()
                    
                    history = []
                    for cmd, resp, ctx, timestamp in results:
                        history.append({
                            'command': cmd,
                            'response': json.loads(resp),
                            'context': json.loads(ctx) if ctx else None,
                            'timestamp': timestamp
                        })
                        
                    return history
                    
        except Exception as e:
            _LOGGER.error(f"Error getting user history: {str(e)}")
            return []

    async def get_similar_commands(self, command: str,
                                 threshold: float = 0.8,
                                 limit: int = 5) -> List[Dict[str, Any]]:
        """Find similar commands from history."""
        try:
            async with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Use simple string matching for now
                    # This could be enhanced with proper text similarity
                    cursor.execute("""
                        SELECT command, response, user_id, created_at
                        FROM commands
                        WHERE command LIKE ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (f"%{command}%", limit))
                    
                    results = cursor.fetchall()
                    
                    similar = []
                    for cmd, resp, uid, timestamp in results:
                        similar.append({
                            'command': cmd,
                            'response': json.loads(resp),
                            'user_id': uid,
                            'timestamp': timestamp
                        })
                        
                    return similar
                    
        except Exception as e:
            _LOGGER.error(f"Error finding similar commands: {str(e)}")
            return []

class UserStorage(BaseStorage):
    async def store_user_preferences(self, user_id: str,
                                   preferences: Dict[str, Any]) -> bool:
        """Store user preferences."""
        try:
            async with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    preferences_json = json.dumps(preferences)
                    
                    cursor.execute("""
                        INSERT INTO users (user_id, preferences)
                        VALUES (?, ?)
                        ON CONFLICT(user_id) DO UPDATE SET preferences = ?
                    """, (user_id, preferences_json, preferences_json))
                    
                    conn.commit()
                    
            return True
            
        except Exception as e:
            _LOGGER.error(f"Error storing user preferences: {str(e)}")
            return False

    async def get_user_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user preferences."""
        try:
            async with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        SELECT preferences FROM users
                        WHERE user_id = ?
                    """, (user_id,))
                    
                    result = cursor.fetchone()
                    
                    if result and result[0]:
                        return json.loads(result[0])
                        
            return None
            
        except Exception as e:
            _LOGGER.error(f"Error getting user preferences: {str(e)}")
            return None

    async def get_active_users(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recently active users."""
        try:
            async with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        SELECT user_id, name, last_seen
                        FROM users
                        WHERE last_seen >= datetime('now', ?)
                        ORDER BY last_seen DESC
                    """, (f'-{days} days',))
                    
                    results = cursor.fetchall()
                    
                    users = []
                    for user_id, name, last_seen in results:
                        users.append({
                            'user_id': user_id,
                            'name': name,
                            'last_seen': last_seen
                        })
                        
                    return users
                    
        except Exception as e:
            _LOGGER.error(f"Error getting active users: {str(e)}")
            return [] 