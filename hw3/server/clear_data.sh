#!/bin/bash

# Clear all data and reset database
# Use this script to clean up test data

echo "==================================================="
echo "         Clear Database Script"
echo "==================================================="

cd "$(dirname "$0")"

echo ""
echo "WARNING: This will delete all data!"
echo "  - All user accounts"
echo "  - All games"
echo "  - All reviews"
echo "  - All rooms"
echo ""

read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Operation cancelled."
    exit 0
fi

echo ""
echo "Clearing database files..."

# Remove data files
rm -f data/dev_users.json
rm -f data/player_users.json
rm -f data/games.json
rm -f data/reviews.json
rm -f data/rooms.json

# Remove uploaded games
rm -rf uploaded_games/*

# Remove player downloads (keep .gitkeep)
echo "Clearing player downloads..."
find ../player/downloads -mindepth 1 -not -name '.gitkeep' -delete

echo ""
echo "Database cleared successfully!"
echo "All player downloads have been removed."
echo "Servers will start with fresh data on next launch."
