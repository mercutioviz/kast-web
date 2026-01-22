#!/bin/bash
# Wrapper script to reset user password with proper permissions
# Usage: sudo ./scripts/reset_password_wrapper.sh

set -e

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ This script must be run with sudo"
    echo "Usage: sudo ./scripts/reset_password_wrapper.sh"
    exit 1
fi

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Check if we're in the right directory
if [ ! -f "$PROJECT_DIR/config.py" ]; then
    echo "❌ Error: Cannot find config.py"
    echo "Please run this script from the kast-web directory"
    exit 1
fi

# Check if virtual environment exists
if [ ! -f "$PROJECT_DIR/venv/bin/python3" ]; then
    echo "❌ Error: Virtual environment not found at $PROJECT_DIR/venv"
    echo "Please ensure the virtual environment is set up correctly"
    exit 1
fi

echo "=== KAST-Web Password Reset Wrapper ==="
echo "Running password reset script as www-data user..."
echo ""

# Run the script as www-data user
sudo -u www-data "$PROJECT_DIR/scripts/reset_password.py"

exit $?
