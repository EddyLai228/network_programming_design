# Game Specification for Game Store Platform

This document defines the unified game specification that all games must follow to be compatible with the Game Store platform.

## Directory Structure

Each game should have the following structure:

```
game_name/
├── game.py          # Main game entry point (or other file specified in config)
├── config.json      # Game configuration (optional if metadata provided during upload)
├── server.py        # Game server (for multiplayer games)
├── client.py        # Game client
├── requirements.txt # Python dependencies (if any)
└── README.md        # Game description and instructions
```

## Configuration File (config.json)

The `config.json` file should contain the following information:

```json
{
  "name": "Game Name",
  "description": "Brief description of the game",
  "type": "CLI|GUI|MULTIPLAYER",
  "max_players": 2,
  "version": "1.0.0",
  "start_command": "python game.py",
  "server_command": "python server.py",
  "client_command": "python client.py --host localhost",
  "dependencies": []
}
```

## Game Types

### 1. CLI Games
- Text-based interface
- Run in terminal
- Support standard input/output
- Example: Tic-Tac-Toe, Guess the Number

### 2. GUI Games
- Graphical user interface
- Use libraries like pygame, tkinter, etc.
- Should handle window closing gracefully
- Example: Snake, Pong

### 3. MULTIPLAYER Games
- Support 3 or more players
- Client-server architecture
- Server manages game state
- Clients connect to server
- Example: Card games, Board games

## Game Lifecycle

### 1. Upload/Update
- Developer packages game directory as zip
- System extracts and stores in `uploaded_games/{game_id}/{version}/`

### 2. Download
- Player requests game download
- System sends game files as zip
- Client extracts to `downloads/{username}/{game_id}/`

### 3. Start
- For CLI/GUI: Direct execution via start_command
- For MULTIPLAYER: 
  - Server starts game server
  - Clients connect to server
  - Game begins when all players ready

## Communication Protocol (for Multiplayer Games)

Multiplayer games should use a simple JSON-based protocol:

### Server Messages
```json
{
  "type": "game_state",
  "data": {
    "players": [...],
    "current_turn": 0,
    "board": [...],
    ...
  }
}
```

### Client Messages
```json
{
  "type": "player_action",
  "data": {
    "action": "move",
    "params": {...}
  }
}
```

## Best Practices

1. **Error Handling**: Always handle errors gracefully
2. **Clean Exit**: Ensure game exits cleanly on Ctrl+C or window close
3. **State Management**: Save/restore game state if needed
4. **Network Timeout**: Handle network timeouts in multiplayer games
5. **Resource Cleanup**: Clean up resources (files, sockets, etc.) on exit

## Testing

Before uploading, test your game:

1. Can it run standalone?
2. Does it handle invalid inputs?
3. Can multiple instances run simultaneously?
4. Does it clean up properly on exit?
