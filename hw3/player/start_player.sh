#!/bin/bash

# Player Client Startup Script

echo "==================================================="
echo "      Game Store System - Lobby Client"
echo "==================================================="

# Default values
SERVER_HOST="localhost"
SERVER_PORT=8002

# Check if arguments provided
if [ $# -ge 1 ]; then
    SERVER_HOST=$1
fi

if [ $# -ge 2 ]; then
    SERVER_PORT=$2
fi

echo ""
echo "Connecting to Lobby Server at $SERVER_HOST:$SERVER_PORT"
echo ""

# Change to player directory
cd "$(dirname "$0")"

# Start client
python3 lobby_client.py $SERVER_HOST $SERVER_PORT
