.PHONY: help run server developer player clean test

# Default target
help:
	@echo "Game Store System - Makefile"
	@echo "============================="
	@echo ""
	@echo "Available targets:"
	@echo "  make run          - Start both servers (alias for 'make server')"
	@echo "  make server       - Start both servers (Developer + Lobby)"
	@echo "  make developer    - Start developer client"
	@echo "  make player       - Start player client"
	@echo "  make clean        - Clear all database and uploaded games"
	@echo "  make test         - Run basic connectivity tests"
	@echo ""
	@echo "To specify server host/port:"
	@echo "  make developer HOST=<ip> PORT=<port>"
	@echo "  make player HOST=<ip> PORT=<port>"

# Start servers (alias)
run: server

# Start servers
server:
	@echo "Starting Game Store Servers..."
	cd server && ./start_servers.sh

# Start developer client
developer:
	@echo "Starting Developer Client..."
	cd developer && ./start_developer.sh $(HOST) $(PORT)

# Start player client
player:
	@echo "Starting Lobby Client..."
	cd player && ./start_player.sh $(HOST) $(PORT)

# Clean database
clean:
	@echo "Cleaning database..."
	cd server && ./clear_data.sh
