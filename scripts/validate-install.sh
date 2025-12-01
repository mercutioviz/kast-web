#!/bin/bash

################################################################################
# KAST-Web Installation Validation Script
# Version: 1.0.0
# Description: Validates KAST-Web installation and generates health report
# Usage: sudo ./scripts/validate-install.sh
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
KAST_CLI_PATH="/usr/local/bin/kast"

# Counters
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0

print_header() {
    echo -e "\n${CYAN}${BOLD}═══════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}${BOLD}  $1${NC}"
    echo -e "${CYAN}${BOLD}═══════════════════════════════════════════════════════${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
    ((CHECKS_PASSED++))
}

print_error() {
    echo -e "${RED}✗${NC} $1"
    ((CHECKS_FAILED++))
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((CHECKS_WARNING++))
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
echo -e "${CYAN}${BOLD}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║                                                       ║"
echo "║     KAST-Web Installation Validation Report          ║"
echo "║                                                       ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}\n"

################################################################################
# Service Checks
################################################################################

print_header "Service Status"

# Redis
if systemctl is-active --quiet redis-server; then
    print_success "Redis server is running"
    if redis-cli ping &>/dev/null; then
        print_success "Redis is responding to ping"
    else
        print_error "Redis is not responding to ping"
    fi
else
    print_error "Redis server is not running"
fi

# Celery Worker
if systemctl is-active --quiet kast-celery; then
    print_success "Celery worker service is running"
else
    print_error "Celery worker service is not running"
fi

# Gunicorn/KAST-Web
if systemctl is-active --quiet kast-web; then
    print_success "KAST-Web (Gunicorn) service is running"
else
    print_error "KAST-Web (Gunicorn) service is not running"
fi

# Web Server
if systemctl is-active --quiet nginx; then
    print_success "Nginx web server is running"
    WEB_SERVER="nginx"
elif systemctl is-active --quiet apache2; then
    print_success "Apache web server is running"
    WEB_SERVER="apache2"
else
    print_error "No web server is running (nginx/apache2)"
    WEB_SERVER="none"
fi

################################################################################
# Port Checks
################################################################################

print_header "Port Availability"

# Check port 8000 (Gunicorn)
if netstat -tlnp 2>/dev/null | grep -q ":8000"; then
    print_success "Port 8000 (Gunicorn) is listening"
elif ss -tlnp 2>/dev/null | grep -q ":8000"; then
    print_success "Port 8000 (Gunicorn) is listening"
else
    print_error "Port 8000 (Gunicorn) is not listening"
fi

# Check port 80 (HTTP)
if netstat -tlnp 2>/dev/null | grep -q ":80"; then
    print_success "Port 80 (HTTP) is listening"
elif ss -tlnp 2>/dev/null | grep -q ":80"; then
    print_success "Port 80 (HTTP) is listening"
else
    print_warning "Port 80 (HTTP) is not listening"
fi

# Check port 6379 (Redis)
if netstat -tlnp 2>/dev/null | grep -q "127.0.0.1:6379"; then
    print_success "Port 6379 (Redis) is listening on localhost"
elif ss -tlnp 2>/dev/null | grep -q "127.0.0.1:6379"; then
    print_success "Port 6379 (Redis) is listening on localhost"
else
    print_error "Port 6379 (Redis) is not listening on localhost"
fi

################################################################################
# File System Checks
################################################################################

print_header "File System"

# Installation directory
if [[ -d "$INSTALL_DIR" ]]; then
    print_success "Installation directory exists: $INSTALL_DIR"
else
    print_error "Installation directory not found: $INSTALL_DIR"
fi

# Virtual environment
if [[ -d "$INSTALL_DIR/venv" ]]; then
    print_success "Python virtual environment exists"
else
    print_error "Python virtual environment not found"
fi

# Configuration file
if [[ -f "$INSTALL_DIR/.env" ]]; then
    print_success "Configuration file exists: .env"
    # Check permissions
    PERMS=$(stat -c "%a" "$INSTALL_DIR/.env")
    if [[ "$PERMS" == "600" ]]; then
        print_success ".env file has correct permissions (600)"
    else
        print_warning ".env file permissions are $PERMS (should be 600)"
    fi
else
    print_error "Configuration file not found: .env"
fi

# Log directory
if [[ -d "/var/log/kast-web" ]]; then
    print_success "Log directory exists"
else
    print_error "Log directory not found"
fi

# Results directory
if [[ -d "$HOME/kast_results" ]]; then
    print_success "Scan results directory exists"
else
    print_warning "Scan results directory not found: $HOME/kast_results"
fi

################################################################################
# Application Checks
################################################################################

print_header "Application"

# HTTP Response
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 2>/dev/null || echo "000")
if [[ "$HTTP_CODE" == "200" ]] || [[ "$HTTP_CODE" == "302" ]]; then
    print_success "Application is responding (HTTP $HTTP_CODE)"
else
    print_error "Application is not responding correctly (HTTP $HTTP_CODE)"
fi

# Database connection
if [[ -f "$INSTALL_DIR/.env" ]]; then
    cd "$INSTALL_DIR"
    if [[ -f "$INSTALL_DIR/venv/bin/activate" ]]; then
        source "$INSTALL_DIR/venv/bin/activate"
        if python3 -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.engine.connect()" 2>/dev/null; then
            print_success "Database connection successful"
        else
            print_error "Database connection failed"
        fi
        deactivate
    else
        print_error "Virtual environment activation script not found"
    fi
fi

################################################################################
# KAST CLI Checks
################################################################################

print_header "KAST CLI Integration"

if [[ -f "$KAST_CLI_PATH" ]]; then
    print_success "KAST CLI found at $KAST_CLI_PATH"
    
    if [[ -x "$KAST_CLI_PATH" ]]; then
        print_success "KAST CLI is executable"
        
        if $KAST_CLI_PATH --version &>/dev/null; then
            VERSION=$($KAST_CLI_PATH --version 2>/dev/null || echo "unknown")
            print_success "KAST CLI is functional (version: $VERSION)"
        else
            print_warning "KAST CLI may not be fully functional"
        fi
        
        if $KAST_CLI_PATH --list-plugins &>/dev/null; then
            PLUGIN_COUNT=$($KAST_CLI_PATH --list-plugins 2>/dev/null | wc -l)
            print_success "KAST CLI plugins detected: $PLUGIN_COUNT"
        else
            print_warning "Cannot list KAST CLI plugins"
        fi
    else
        print_error "KAST CLI is not executable"
    fi
else
    print_error "KAST CLI not found at $KAST_CLI_PATH"
fi

################################################################################
# Web Server Configuration
################################################################################

print_header "Web Server Configuration"

if [[ "$WEB_SERVER" == "nginx" ]]; then
    if [[ -f "/etc/nginx/sites-available/kast-web" ]]; then
        print_success "Nginx configuration file exists"
        
        if [[ -L "/etc/nginx/sites-enabled/kast-web" ]]; then
            print_success "Nginx configuration is enabled"
        else
            print_warning "Nginx configuration is not enabled"
        fi
        
        if nginx -t &>/dev/null; then
            print_success "Nginx configuration is valid"
        else
            print_error "Nginx configuration test failed"
        fi
    else
        print_error "Nginx configuration file not found"
    fi
elif [[ "$WEB_SERVER" == "apache2" ]]; then
    if [[ -f "/etc/apache2/sites-available/kast-web.conf" ]]; then
        print_success "Apache configuration file exists"
        
        if [[ -L "/etc/apache2/sites-enabled/kast-web.conf" ]]; then
            print_success "Apache configuration is enabled"
        else
            print_warning "Apache configuration is not enabled"
        fi
        
        if apache2ctl -t &>/dev/null; then
            print_success "Apache configuration is valid"
        else
            print_error "Apache configuration test failed"
        fi
    else
        print_error "Apache configuration file not found"
    fi
fi

################################################################################
# Systemd Configuration
################################################################################

print_header "Systemd Configuration"

if [[ -f "/etc/systemd/system/kast-web.service" ]]; then
    print_success "kast-web.service file exists"
    
    if systemctl is-enabled --quiet kast-web; then
        print_success "kast-web.service is enabled"
    else
        print_warning "kast-web.service is not enabled"
    fi
else
    print_error "kast-web.service file not found"
fi

if [[ -f "/etc/systemd/system/kast-celery.service" ]]; then
    print_success "kast-celery.service file exists"
    
    if systemctl is-enabled --quiet kast-celery; then
        print_success "kast-celery.service is enabled"
    else
        print_warning "kast-celery.service is not enabled"
    fi
else
    print_error "kast-celery.service file not found"
fi

################################################################################
# Summary
################################################################################

print_header "Validation Summary"

TOTAL_CHECKS=$((CHECKS_PASSED + CHECKS_FAILED + CHECKS_WARNING))

echo -e "${BOLD}Results:${NC}"
echo -e "  ${GREEN}Passed:${NC}   $CHECKS_PASSED"
echo -e "  ${RED}Failed:${NC}   $CHECKS_FAILED"
echo -e "  ${YELLOW}Warnings:${NC} $CHECKS_WARNING"
echo -e "  ${BLUE}Total:${NC}    $TOTAL_CHECKS"

echo ""

if [[ $CHECKS_FAILED -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}✓ Installation validation completed successfully!${NC}"
    echo -e "${GREEN}  All critical checks passed.${NC}"
    EXIT_CODE=0
else
    echo -e "${RED}${BOLD}✗ Installation validation found $CHECKS_FAILED issue(s).${NC}"
    echo -e "${RED}  Please review the errors above and fix them.${NC}"
    EXIT_CODE=1
fi

if [[ $CHECKS_WARNING -gt 0 ]]; then
    echo -e "${YELLOW}  There are $CHECKS_WARNING warning(s) that should be reviewed.${NC}"
fi

echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo "  View service logs:     sudo journalctl -u kast-web -f"
echo "  Restart services:      sudo systemctl restart kast-web kast-celery"
echo "  Check service status:  sudo systemctl status kast-web kast-celery"

echo ""

exit $EXIT_CODE
