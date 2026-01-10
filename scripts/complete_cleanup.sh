#!/bin/bash

################################################################################
# KAST-Web Complete Cleanup Script (Test Environment)
# Version: 1.0.0
# Description: Removes all KAST-Web files without touching system dependencies
# Usage: sudo ./scripts/complete_cleanup.sh
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
    print_error "This script must be run as root or with sudo"
    exit 1
fi

# Print banner
echo -e "${RED}${BOLD}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║                                                       ║"
echo "║      KAST-Web Complete Cleanup Script                 ║"
echo "║      (Test Environment - Preserves Dependencies)      ║"
echo "║                                                       ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}\n"

print_warning "This script will completely remove KAST-Web from your system."
print_info "System dependencies (Redis, Python, Docker, Nginx) will be preserved."
echo ""

# Confirmation prompt
read -p "Are you sure you want to proceed? Type 'yes' to continue: " -r confirm
if [[ ! "$confirm" == "yes" ]]; then
    print_info "Cleanup cancelled"
    exit 0
fi

echo ""
BACKUP_CREATED=false
BACKUP_DIR="/tmp/kast-web-backup-$(date +%Y%m%d-%H%M%S)"

read -p "Create a quick backup before cleanup? (Y/n): " -r backup_choice
if [[ ! "$backup_choice" =~ ^[Nn]$ ]]; then
    mkdir -p "$BACKUP_DIR"
    
    # Backup database if exists
    if [[ -f "/var/lib/kast-web/kast.db" ]]; then
        cp /var/lib/kast-web/kast.db "$BACKUP_DIR/" 2>/dev/null || true
        print_success "Database backed up to $BACKUP_DIR/"
    fi
    
    # Backup .env if exists
    if [[ -f "/opt/kast-web/.env" ]]; then
        cp /opt/kast-web/.env "$BACKUP_DIR/" 2>/dev/null || true
        print_success "Environment file backed up"
    fi
    
    BACKUP_CREATED=true
fi

################################################################################
# 1. Stop Services
################################################################################

print_header "Step 1: Stopping Services"

if systemctl is-active --quiet kast-web 2>/dev/null; then
    systemctl stop kast-web
    print_success "Stopped kast-web service"
else
    print_info "kast-web service not running"
fi

if systemctl is-active --quiet kast-celery 2>/dev/null; then
    systemctl stop kast-celery
    print_success "Stopped kast-celery service"
else
    print_info "kast-celery service not running"
fi

# Disable services
if systemctl is-enabled --quiet kast-web 2>/dev/null; then
    systemctl disable kast-web 2>/dev/null || true
    print_success "Disabled kast-web service"
fi

if systemctl is-enabled --quiet kast-celery 2>/dev/null; then
    systemctl disable kast-celery 2>/dev/null || true
    print_success "Disabled kast-celery service"
fi

################################################################################
# 2. Remove Systemd Service Files
################################################################################

print_header "Step 2: Removing Systemd Service Files"

if [[ -f "/etc/systemd/system/kast-web.service" ]]; then
    rm -f /etc/systemd/system/kast-web.service
    print_success "Removed /etc/systemd/system/kast-web.service"
else
    print_info "kast-web.service not found"
fi

if [[ -f "/etc/systemd/system/kast-celery.service" ]]; then
    rm -f /etc/systemd/system/kast-celery.service
    print_success "Removed /etc/systemd/system/kast-celery.service"
else
    print_info "kast-celery.service not found"
fi

systemctl daemon-reload
print_success "Reloaded systemd daemon"

################################################################################
# 3. Remove Web Server Configuration
################################################################################

print_header "Step 3: Removing Web Server Configuration"

# Nginx
NGINX_REMOVED=false
if [[ -f "/etc/nginx/sites-enabled/kast-web" ]]; then
    rm -f /etc/nginx/sites-enabled/kast-web
    print_success "Removed Nginx enabled site"
    NGINX_REMOVED=true
fi

if [[ -f "/etc/nginx/sites-available/kast-web" ]]; then
    rm -f /etc/nginx/sites-available/kast-web
    print_success "Removed Nginx available site"
    NGINX_REMOVED=true
fi

if [[ "$NGINX_REMOVED" == true ]]; then
    if systemctl is-active --quiet nginx 2>/dev/null; then
        systemctl reload nginx 2>/dev/null || true
        print_success "Reloaded Nginx"
    fi
else
    print_info "No Nginx configuration found"
fi

# Apache
APACHE_REMOVED=false
if [[ -f "/etc/apache2/sites-enabled/kast-web.conf" ]]; then
    a2dissite kast-web.conf 2>/dev/null || true
    print_success "Disabled Apache site"
    APACHE_REMOVED=true
fi

if [[ -f "/etc/apache2/sites-available/kast-web.conf" ]]; then
    rm -f /etc/apache2/sites-available/kast-web.conf
    print_success "Removed Apache configuration"
    APACHE_REMOVED=true
fi

if [[ "$APACHE_REMOVED" == true ]]; then
    if systemctl is-active --quiet apache2 2>/dev/null; then
        systemctl reload apache2 2>/dev/null || true
        print_success "Reloaded Apache"
    fi
else
    print_info "No Apache configuration found"
fi

################################################################################
# 4. Remove Application Directories
################################################################################

print_header "Step 4: Removing Application Directories"

# /opt/kast-web
if [[ -d "/opt/kast-web" ]]; then
    rm -rf /opt/kast-web
    print_success "Removed /opt/kast-web"
else
    print_info "/opt/kast-web not found"
fi

# /var/lib/kast-web
if [[ -d "/var/lib/kast-web" ]]; then
    rm -rf /var/lib/kast-web
    print_success "Removed /var/lib/kast-web"
else
    print_info "/var/lib/kast-web not found"
fi

# /var/log/kast-web
if [[ -d "/var/log/kast-web" ]]; then
    rm -rf /var/log/kast-web
    print_success "Removed /var/log/kast-web"
else
    print_info "/var/log/kast-web not found"
fi

# /var/run/kast-web
if [[ -d "/var/run/kast-web" ]]; then
    rm -rf /var/run/kast-web
    print_success "Removed /var/run/kast-web"
else
    print_info "/var/run/kast-web not found"
fi

################################################################################
# 5. Remove User and Group
################################################################################

print_header "Step 5: Removing KAST-Web User/Group"

USER_REMOVED=false
if id kast-web &>/dev/null; then
    userdel kast-web 2>/dev/null || true
    print_success "Removed kast-web user"
    USER_REMOVED=true
else
    print_info "kast-web user not found"
fi

if getent group kast-web &>/dev/null; then
    groupdel kast-web 2>/dev/null || true
    print_success "Removed kast-web group"
else
    print_info "kast-web group not found"
fi

################################################################################
# 6. Remove Environment Files
################################################################################

print_header "Step 6: Removing Environment Files"

ENV_REMOVED=false
if [[ -f "/etc/kast-web.env" ]]; then
    rm -f /etc/kast-web.env
    print_success "Removed /etc/kast-web.env"
    ENV_REMOVED=true
fi

if [[ -f "/etc/default/kast-web" ]]; then
    rm -f /etc/default/kast-web
    print_success "Removed /etc/default/kast-web"
    ENV_REMOVED=true
fi

if [[ "$ENV_REMOVED" == false ]]; then
    print_info "No environment files found"
fi

################################################################################
# 7. Optional: Clear Redis KAST-Web Keys
################################################################################

print_header "Step 7: Redis Cleanup (Optional)"

if command -v redis-cli &>/dev/null; then
    if redis-cli ping &>/dev/null; then
        echo ""
        print_warning "Redis is running. KAST-Web may have stored Celery task data."
        read -p "Do you want to clear KAST-Web specific Redis keys? (y/N): " -r clear_redis
        
        if [[ "$clear_redis" =~ ^[Yy]$ ]]; then
            # Clear Celery keys
            CELERY_KEYS=$(redis-cli KEYS "celery*" 2>/dev/null | wc -l)
            if [[ "$CELERY_KEYS" -gt 0 ]]; then
                redis-cli KEYS "celery*" | xargs redis-cli DEL &>/dev/null || true
                print_success "Cleared $CELERY_KEYS Celery keys from Redis"
            else
                print_info "No Celery keys found in Redis"
            fi
            
            # Clear any kast-web specific keys
            KAST_KEYS=$(redis-cli KEYS "*kast*" 2>/dev/null | wc -l)
            if [[ "$KAST_KEYS" -gt 0 ]]; then
                redis-cli KEYS "*kast*" | xargs redis-cli DEL &>/dev/null || true
                print_success "Cleared $KAST_KEYS KAST-Web keys from Redis"
            else
                print_info "No KAST-Web keys found in Redis"
            fi
        else
            print_info "Redis keys preserved"
        fi
    else
        print_info "Redis not responding (may not be running)"
    fi
else
    print_info "redis-cli not found"
fi

################################################################################
# 8. Verification
################################################################################

print_header "Step 8: Verification"

REMAINING_FILES=$(find /opt /var/lib /var/log /var/run /etc -name "*kast-web*" 2>/dev/null | wc -l)

echo "Checking for remaining KAST-Web files..."
if [[ "$REMAINING_FILES" -eq 0 ]]; then
    print_success "No KAST-Web files found"
else
    print_warning "Found $REMAINING_FILES remaining file(s):"
    find /opt /var/lib /var/log /var/run /etc -name "*kast-web*" 2>/dev/null | head -10
fi

# Check services
SERVICES_REMAINING=$(systemctl list-units --all | grep -c "kast" || true)
if [[ "$SERVICES_REMAINING" -eq 0 ]]; then
    print_success "No KAST-Web services found"
else
    print_warning "Found lingering service references (this is usually harmless)"
fi

# Check user
if id kast-web &>/dev/null; then
    print_warning "kast-web user still exists"
else
    print_success "kast-web user removed"
fi

# Check web configs
NGINX_CONFIGS=$(find /etc/nginx -name "*kast*" 2>/dev/null | wc -l)
APACHE_CONFIGS=$(find /etc/apache2 -name "*kast*" 2>/dev/null | wc -l)

if [[ "$NGINX_CONFIGS" -eq 0 ]]; then
    print_success "No Nginx KAST-Web configs found"
else
    print_warning "Found $NGINX_CONFIGS Nginx config file(s)"
fi

if [[ "$APACHE_CONFIGS" -eq 0 ]]; then
    print_success "No Apache KAST-Web configs found"
else
    print_warning "Found $APACHE_CONFIGS Apache config file(s)"
fi

################################################################################
# Summary
################################################################################

print_header "Cleanup Summary"

echo -e "${GREEN}${BOLD}✓ KAST-Web has been completely removed!${NC}"
echo ""

echo -e "${CYAN}What was removed:${NC}"
echo "  ✓ Systemd service files (kast-web.service, kast-celery.service)"
echo "  ✓ Web server configuration (Nginx/Apache KAST-Web sites)"
echo "  ✓ Application directory (/opt/kast-web)"
echo "  ✓ Data directory (/var/lib/kast-web)"
echo "  ✓ Log directory (/var/log/kast-web)"
echo "  ✓ Runtime directory (/var/run/kast-web)"
if [[ "$USER_REMOVED" == true ]]; then
    echo "  ✓ KAST-Web user and group"
fi
if [[ "$ENV_REMOVED" == true ]]; then
    echo "  ✓ Environment files"
fi

echo ""
echo -e "${CYAN}What was preserved:${NC}"
echo "  • Redis server and data"
echo "  • Python and system packages"
echo "  • Docker and containers"
echo "  • Nginx/Apache web server"
echo "  • Other system dependencies"

if [[ "$BACKUP_CREATED" == true ]]; then
    echo ""
    echo -e "${YELLOW}Backup Information:${NC}"
    echo "  Location: $BACKUP_DIR"
    echo "  Contains: Database and configuration files"
fi

echo ""
echo -e "${GREEN}${BOLD}System is ready for a fresh KAST-Web installation!${NC}"
echo ""
print_info "You can now run: sudo ./install.sh"
echo ""
