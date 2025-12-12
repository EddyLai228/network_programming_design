#!/bin/bash

# Start Server Script
# This script starts both Developer Server and Lobby Server

# Trap Ctrl+C and cleanup
cleanup() {
    echo ""
    echo "Stopping servers..."
    if [ ! -z "$DEV_SERVER_PID" ]; then
        kill $DEV_SERVER_PID 2>/dev/null
        echo "Developer Server stopped"
    fi
    if [ ! -z "$LOBBY_SERVER_PID" ]; then
        kill $LOBBY_SERVER_PID 2>/dev/null
        echo "Lobby Server stopped"
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "==================================================="
echo "       Game Store System - Server Startup"
echo "==================================================="

# Change to server directory
cd "$(dirname "$0")"

echo ""
echo "Starting Developer Server on port 8001..."
python3 developer_server.py &
DEV_SERVER_PID=$!
echo "Developer Server PID: $DEV_SERVER_PID"

sleep 2

echo ""
echo "Starting Lobby Server on port 8002..."
python3 lobby_server.py &
LOBBY_SERVER_PID=$!
echo "Lobby Server PID: $LOBBY_SERVER_PID"

echo ""
echo "==================================================="
echo "Both servers are now running!"
echo "Developer Server: Port 8001"
echo "Lobby Server: Port 8002"
echo "==================================================="
echo ""
echo "Press Ctrl+C to stop all servers..."

# Keep script running and wait for Ctrl+C
while true; do
    sleep 1
done
