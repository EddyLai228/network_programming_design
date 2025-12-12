#!/bin/bash

# Developer Client Startup Script

echo "==================================================="
echo "    Game Store System - Developer Client"
echo "==================================================="

# Default values
SERVER_HOST="localhost"
SERVER_PORT=8001

# Check if arguments provided
if [ $# -ge 1 ]; then
    SERVER_HOST=$1
fi

if [ $# -ge 2 ]; then
    SERVER_PORT=$2
fi

echo ""
echo "Connecting to Developer Server at $SERVER_HOST:$SERVER_PORT"
echo ""

# Change to developer directory
cd "$(dirname "$0")"

# Start client
python3 developer_client.py $SERVER_HOST $SERVER_PORT
