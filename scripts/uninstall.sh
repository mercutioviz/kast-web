#!/bin/bash

################################################################################
# KAST-Web Uninstall Script
# Version: 1.0.0
# Description: Safely removes KAST-Web installation
# Usage: sudo ./scripts/uninstall.sh
################################################################################

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

INSTALL_DIR="/opt/kast-web"
BACKUP_DIR="/opt/kast-web-uninstall-backup-$(date +%Y%m%d-%H%M%S)"

print_header() {
    echo -e "\n${CYAN}${BOLD}═══════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}${BOLD}  $1${NC}"
    echo -e "${CYAN}${BOLD}═══════════════════════════════════════════════════════${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}This script must be run as root or with sudo${NC}"
    exit 1
fi

# Print banner
echo -e "${RED}${BOLD}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║                                                       ║"
echo "║          KAST-Web Uninstall Script v1.0               ║"
echo "║                                                       ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}\n"

print_warning "This script will remove KAST-Web from your system."
echo ""

# Confirmation prompt
read -p "Are you sure you want to uninstall KAST-Web? (yes/no): " -r confirm
if [[ ! "$confirm" =~ ^[Yy][Ee][Ss]$ ]]; then
    print_info "Uninstall cancelled"
    exit 0
fi

echo ""
read -p "Do you want to create a backup before uninstalling? (Y/n): " -r backup_choice
CREATE_BACKUP="yes"
if [[ "$backup_choice" =~ ^[Nn]$ ]]; then
    CREATE_BACKUP="no"
fi

################################################################################
# Backup
################################################################################

if [[ "$CREATE_BACKUP" == "yes" ]]; then
    print_header "Creating Backup"
    
    mkdir -p "$BACKUP_DIR"
    print_info "Backup directory: $BACKUP_DIR"
    
    # Backup database
    if [[ -f "$INSTALL_DIR/.env" ]]; then
        source "$INSTALL_DIR/.env"
        
        if [[ "$DATABASE_URL" =~ ^sqlite:/// ]]; then
            DB_PATH="${DATABASE_URL#sqlite:///}"
            if [[ -f "$DB_PATH" ]]; then
                cp "$DB_PATH" "$BACKUP_DIR/"
                print_success "SQLite database backed up"
            fi
        elif [[ "$DATABASE_URL" =~ ^postgresql:// ]]; then
            DB_NAME=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
            sudo -u postgres pg_dump "$DB_NAME" > "$BACKUP_DIR/database.sql" 2>/dev/null || true
            print_success "PostgreSQL database dumped"
        elif [[ "$DATABASE_URL" =~ ^mysql:// ]]; then
            DB_NAME=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
            DB_USER=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
            DB_PASS=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
            mysqldump -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" > "$BACKUP_DIR/database.sql" 2>/dev/null || true
            print_success "MySQL database dumped"
        fi
    fi
    
    # Backup configuration
    [[ -f "$INSTALL_DIR/.env" ]] && cp "$INSTALL_DIR/.env" "$BACKUP_DIR/"
    
    # Backup uploads
    if [[ -d "$INSTALL_DIR/app/static/uploads" ]]; then
        cp -r "$INSTALL_DIR/app/static/uploads" "$BACKUP_DIR/" 2>/dev/null || true
        print_success "Upload files backed up"
    fi
    
    # Create backup info
    cat > "$BACKUP_DIR/backup-info.txt" << EOF
Backup created during uninstall: $(date)
Original installation directory: $INSTALL_DIR
Backup directory: $BACKUP_DIR
EOF
    
    print_success "Backup completed"
fi

################################################################################
# Stop Services
################################################################################

print_header "Stopping Services"

# Stop systemd services
if systemctl is-active --quiet kast-web; then
    systemctl stop kast-web
    print_success "Stopped kast-web service"
fi

if systemctl is-active --quiet kast-celery; then
    systemctl stop kast-celery
    print_success "Stopped kast-celery service"
fi

# Disable services
if systemctl is-enabled --quiet kast-web 2>/dev/null; then
    systemctl disable kast-web
    print_success "Disabled kast-web service"
fi

if systemctl is-enabled --quiet kast-celery 2>/dev/null; then
    systemctl disable kast-celery
    print_success "Disabled kast-celery service"
fi

################################################################################
# Remove Systemd Service Files
################################################################################

print_header "Removing Service Files"

if [[ -f "/etc/systemd/system/kast-web.service" ]]; then
    rm -f /etc/systemd/system/kast-web.service
    print_success "Removed kast-web.service"
fi

if [[ -f "/etc/systemd/system/kast-celery.service" ]]; then
    rm -f /etc/systemd/system/kast-celery.service
    print_success "Removed kast-celery.service"
fi

systemctl daemon-reload
print_success "Reloaded systemd daemon"

################################################################################
# Remove Web Server Configuration
################################################################################

print_header "Removing Web Server Configuration"

# Nginx
if [[ -f "/etc/nginx/sites-enabled/kast-web" ]]; then
    rm -f /etc/nginx/sites-enabled/kast-web
    print_success "Removed Nginx enabled site"
fi

if [[ -f "/etc/nginx/sites-available/kast-web" ]]; then
    rm -f /etc/nginx/sites-available/kast-web
    print_success "Removed Nginx configuration"
    
    if systemctl is-active --quiet nginx; then
        systemctl reload nginx
        print_success "Reloaded Nginx"
    fi
fi

# Apache
if [[ -f "/etc/apache2/sites-enabled/kast-web.conf" ]]; then
    a2dissite kast-web.conf 2>/dev/null || true
    print_success "Disabled Apache site"
fi

if [[ -f "/etc/apache2/sites-available/kast-web.conf" ]]; then
    rm -f /etc/apache2/sites-available/kast-web.conf
    print_success "Removed Apache configuration"
    
    if systemctl is-active --quiet apache2; then
        systemctl reload apache2
        print_success "Reloaded Apache"
    fi
fi

################################################################################
# Remove Application Files
################################################################################

print_header "Removing Application Files"

read -p "Remove application directory ($INSTALL_DIR)? (Y/n): " -r remove_app
if [[ ! "$remove_app" =~ ^[Nn]$ ]]; then
    if [[ -d "$INSTALL_DIR" ]]; then
        rm -rf "$INSTALL_DIR"
        print_success "Removed application directory"
    fi
else
    print_info "Application directory preserved"
fi

# Remove log directory
read -p "Remove log files (/var/log/kast-web)? (Y/n): " -r remove_logs
if [[ ! "$remove_logs" =~ ^[Nn]$ ]]; then
    if [[ -d "/var/log/kast-web" ]]; then
        rm -rf /var/log/kast-web
        print_success "Removed log directory"
    fi
else
    print_info "Log directory preserved"
fi

# Remove runtime directory
if [[ -d "/var/run/kast-web" ]]; then
    rm -rf /var/run/kast-web
    print_success "Removed runtime directory"
fi

################################################################################
# Database Cleanup
################################################################################

print_header "Database Cleanup"

if [[ -f "$BACKUP_DIR/../.env" ]] || [[ -f "$INSTALL_DIR/.env" ]]; then
    # Try to load DATABASE_URL from backup or existing .env
    if [[ -f "$BACKUP_DIR/.env" ]]; then
        source "$BACKUP_DIR/.env"
    elif [[ -f "$INSTALL_DIR/.env" ]]; then
        source "$INSTALL_DIR/.env"
    fi
    
    if [[ -n "$DATABASE_URL" ]]; then
        echo ""
        echo "Database configuration detected: $DATABASE_URL"
        read -p "Do you want to remove the database? (y/N): " -r remove_db
        
        if [[ "$remove_db" =~ ^[Yy]$ ]]; then
            if [[ "$DATABASE_URL" =~ ^postgresql:// ]]; then
                DB_NAME=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
                DB_USER=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
                
                sudo -u postgres psql << EOF 2>/dev/null || true
DROP DATABASE IF EXISTS $DB_NAME;
DROP USER IF EXISTS $DB_USER;
EOF
                print_success "Removed PostgreSQL database and user"
                
            elif [[ "$DATABASE_URL" =~ ^mysql:// ]]; then
                DB_NAME=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
                DB_USER=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
                DB_PASS=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
                
                mysql << EOF 2>/dev/null || true
DROP DATABASE IF EXISTS $DB_NAME;
DROP USER IF EXISTS '$DB_USER'@'localhost';
FLUSH PRIVILEGES;
EOF
                print_success "Removed MySQL database and user"
                
            elif [[ "$DATABASE_URL" =~ ^sqlite:/// ]]; then
                DB_PATH="${DATABASE_URL#sqlite:///}"
                if [[ -f "$DB_PATH" ]]; then
                    rm -f "$DB_PATH"
                    print_success "Removed SQLite database file"
                fi
            fi
        else
            print_info "Database preserved"
        fi
    fi
fi

################################################################################
# Optional: Remove Dependencies
################################################################################

print_header "System Dependencies"

echo ""
echo "The following system packages were installed by the installer:"
echo "  - Redis (redis-server)"
echo "  - Python dependencies (python3, python3-pip, python3-venv, etc.)"
echo "  - Build tools (build-essential)"
echo "  - Database servers (if PostgreSQL/MySQL/MariaDB was installed)"
echo ""
print_warning "These packages may be used by other applications on your system."
read -p "Do you want to remove these packages? (y/N): " -r remove_deps

if [[ "$remove_deps" =~ ^[Yy]$ ]]; then
    print_warning "Removing system packages..."
    
    # Stop Redis if not used by other services
    if systemctl is-active --quiet redis-server; then
        read -p "Stop and remove Redis? (y/N): " -r remove_redis
        if [[ "$remove_redis" =~ ^[Yy]$ ]]; then
            systemctl stop redis-server
            systemctl disable redis-server
            apt-get remove -y redis-server 2>/dev/null || true
            print_success "Removed Redis"
        fi
    fi
    
    print_info "Other system packages preserved (remove manually if needed)"
else
    print_info "System packages preserved"
fi

################################################################################
# Summary
################################################################################

print_header "Uninstall Summary"

echo -e "${GREEN}${BOLD}KAST-Web has been uninstalled.${NC}"
echo ""

if [[ "$CREATE_BACKUP" == "yes" ]]; then
    echo -e "${CYAN}Backup Information:${NC}"
    echo "  Location: $BACKUP_DIR"
    echo "  Contains: Database, configuration, and uploaded files"
    echo ""
fi

echo -e "${CYAN}What was removed:${NC}"
echo "  ✓ Systemd service files"
echo "  ✓ Web server configuration"
if [[ ! "$remove_app" =~ ^[Nn]$ ]]; then
    echo "  ✓ Application files"
fi
if [[ ! "$remove_logs" =~ ^[Nn]$ ]]; then
    echo "  ✓ Log files"
fi

echo ""
echo -e "${CYAN}What was preserved:${NC}"
if [[ "$remove_app" =~ ^[Nn]$ ]]; then
    echo "  • Application directory: $INSTALL_DIR"
fi
if [[ "$remove_logs" =~ ^[Nn]$ ]]; then
    echo "  • Log directory: /var/log/kast-web"
fi
if [[ ! "$remove_db" =~ ^[Yy]$ ]]; then
    echo "  • Database (if applicable)"
fi
if [[ ! "$remove_deps" =~ ^[Yy]$ ]]; then
    echo "  • System dependencies"
fi

echo ""
print_info "Thank you for using KAST-Web!"
echo ""
