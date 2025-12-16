#!/bin/bash

################################################################################
# KAST-Web Rollback Script
# Version: 1.0.0
# Description: Quick rollback utility for KAST-Web deployments
# Usage: sudo ./scripts/rollback.sh [backup-directory]
################################################################################

set -e  # Exit on error
set -o pipefail  # Catch errors in pipes

################################################################################
# Configuration Variables
################################################################################

INSTALL_DIR="/opt/kast-web"
BACKUP_BASE_DIR="/opt/kast-web-backup"
LOG_FILE="/var/log/kast-web/rollback.log"
SERVICE_USER="www-data"
VENV_DIR="$INSTALL_DIR/venv"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

################################################################################
# Utility Functions
################################################################################

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}" | tee -a "$LOG_FILE"
}

print_error() {
    echo -e "${RED}✗ $1${NC}" | tee -a "$LOG_FILE"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}" | tee -a "$LOG_FILE"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}" | tee -a "$LOG_FILE"
}

print_header() {
    echo -e "\n${CYAN}${BOLD}═══════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}${BOLD}  $1${NC}"
    echo -e "${CYAN}${BOLD}═══════════════════════════════════════════════════════${NC}\n"
}

# Error handler
error_exit() {
    print_error "$1"
    log "Rollback failed. Check $LOG_FILE for details."
    exit 1
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error_exit "This script must be run as root or with sudo"
    fi
}

################################################################################
# Backup Selection
################################################################################

list_available_backups() {
    print_header "Available Backups"
    
    # Find all backup directories
    BACKUPS=($(ls -dt ${BACKUP_BASE_DIR}-* 2>/dev/null || true))
    
    if [[ ${#BACKUPS[@]} -eq 0 ]]; then
        print_warning "No backups found"
        return 1
    fi
    
    echo -e "${CYAN}${BOLD}Found ${#BACKUPS[@]} backup(s):${NC}\n"
    
    local index=1
    for backup in "${BACKUPS[@]}"; do
        local backup_name=$(basename "$backup")
        local backup_date=$(echo "$backup_name" | sed 's/.*-\([0-9]\{8\}\)-\([0-9]\{6\}\)/\1 \2/' | sed 's/\([0-9]\{4\}\)\([0-9]\{2\}\)\([0-9]\{2\}\) \([0-9]\{2\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)/\1-\2-\3 \4:\5:\6/')
        
        echo -e "  ${BOLD}[$index]${NC} $backup_name"
        echo "      Date: $backup_date"
        
        # Show backup info if available
        if [[ -f "$backup/backup-info.txt" ]]; then
            local version=$(grep "Current version:" "$backup/backup-info.txt" 2>/dev/null | cut -d: -f2 | xargs)
            local update_type=$(grep "Update type:" "$backup/backup-info.txt" 2>/dev/null | cut -d: -f2 | xargs)
            [[ -n "$version" ]] && echo "      Version: $version"
            [[ -n "$update_type" ]] && echo "      Type: $update_type"
        fi
        
        echo ""
        ((index++))
    done
    
    return 0
}

select_backup() {
    if [[ -n "$1" ]]; then
        # Backup directory provided as argument
        SELECTED_BACKUP="$1"
        
        if [[ ! -d "$SELECTED_BACKUP" ]]; then
            error_exit "Backup directory not found: $SELECTED_BACKUP"
        fi
        
        print_info "Using specified backup: $(basename $SELECTED_BACKUP)"
    else
        # Interactive selection
        if ! list_available_backups; then
            error_exit "No backups available for rollback"
        fi
        
        echo -e "${CYAN}${BOLD}Select a backup to restore:${NC}"
        read -p "Enter backup number (1-${#BACKUPS[@]}), or 'q' to quit: " -r selection
        
        if [[ "$selection" == "q" ]] || [[ "$selection" == "Q" ]]; then
            print_info "Rollback cancelled by user"
            exit 0
        fi
        
        if ! [[ "$selection" =~ ^[0-9]+$ ]] || [[ $selection -lt 1 ]] || [[ $selection -gt ${#BACKUPS[@]} ]]; then
            error_exit "Invalid selection: $selection"
        fi
        
        SELECTED_BACKUP="${BACKUPS[$((selection-1))]}"
        print_success "Selected backup: $(basename $SELECTED_BACKUP)"
    fi
}

################################################################################
# Backup Validation
################################################################################

validate_backup() {
    print_header "Validating Backup"
    
    if [[ ! -d "$SELECTED_BACKUP" ]]; then
        error_exit "Backup directory does not exist: $SELECTED_BACKUP"
    fi
    
    print_success "Backup directory exists"
    
    # Check for backup info
    if [[ -f "$SELECTED_BACKUP/backup-info.txt" ]]; then
        print_success "Backup metadata found"
        echo ""
        cat "$SELECTED_BACKUP/backup-info.txt" | while read line; do
            echo "  $line"
        done
        echo ""
    else
        print_warning "Backup metadata not found"
    fi
    
    # Check for git commit
    if [[ -f "$SELECTED_BACKUP/git-commit.txt" ]]; then
        RESTORE_COMMIT=$(cat "$SELECTED_BACKUP/git-commit.txt")
        print_success "Git commit found: $(echo $RESTORE_COMMIT | cut -c1-7)"
    else
        print_warning "Git commit reference not found"
        RESTORE_COMMIT=""
    fi
    
    # Check for database backup
    local db_found=0
    if [[ -f "$SELECTED_BACKUP/.env" ]]; then
        source "$SELECTED_BACKUP/.env"
        
        if [[ "$DATABASE_URL" =~ ^sqlite:/// ]]; then
            DB_PATH="${DATABASE_URL#sqlite:///}"
            DB_FILE=$(basename "$DB_PATH")
            if [[ -f "$SELECTED_BACKUP/$DB_FILE" ]]; then
                print_success "SQLite database backup found"
                db_found=1
            fi
        elif [[ -f "$SELECTED_BACKUP/database.sql" ]]; then
            print_success "Database dump found"
            db_found=1
        fi
    fi
    
    if [[ $db_found -eq 0 ]]; then
        print_warning "Database backup not found"
    fi
    
    # Check for configuration
    if [[ -f "$SELECTED_BACKUP/.env" ]]; then
        print_success "Configuration backup found"
    else
        print_warning "Configuration backup not found"
    fi
}

################################################################################
# Rollback Execution
################################################################################

stop_services() {
    print_header "Stopping Services"
    
    # Stop web application
    if systemctl is-active --quiet kast-web; then
        print_info "Stopping web application..."
        systemctl stop kast-web >> "$LOG_FILE" 2>&1
        print_success "Web application stopped"
    else
        print_info "Web application already stopped"
    fi
    
    # Stop Celery worker
    if systemctl is-active --quiet kast-celery; then
        print_info "Stopping Celery worker..."
        systemctl stop kast-celery >> "$LOG_FILE" 2>&1
        print_success "Celery worker stopped"
    else
        print_info "Celery worker already stopped"
    fi
}

restore_git_state() {
    if [[ -z "$RESTORE_COMMIT" ]]; then
        print_warning "No git commit to restore"
        return 0
    fi
    
    print_header "Restoring Git State"
    
    cd "$INSTALL_DIR" || error_exit "Failed to change to installation directory"
    
    # Check if we're in a git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_warning "Not a git repository, skipping git restore"
        return 0
    fi
    
    print_info "Resetting to commit: $(echo $RESTORE_COMMIT | cut -c1-7)"
    
    if git reset --hard "$RESTORE_COMMIT" >> "$LOG_FILE" 2>&1; then
        print_success "Git state restored"
        
        # Show version after restore
        if [[ -f "$INSTALL_DIR/config.py" ]]; then
            RESTORED_VERSION=$(grep "^VERSION = " "$INSTALL_DIR/config.py" | cut -d"'" -f2)
            print_info "Restored version: $RESTORED_VERSION"
        fi
    else
        print_error "Git reset failed"
        print_warning "Continuing with rollback..."
    fi
}

restore_database() {
    print_header "Restoring Database"
    
    if [[ ! -f "$SELECTED_BACKUP/.env" ]]; then
        print_warning "No .env file in backup, skipping database restore"
        return 0
    fi
    
    source "$SELECTED_BACKUP/.env"
    
    if [[ "$DATABASE_URL" =~ ^sqlite:/// ]]; then
        # SQLite restoration
        DB_PATH="${DATABASE_URL#sqlite:///}"
        DB_FILE=$(basename "$DB_PATH")
        
        if [[ -f "$SELECTED_BACKUP/$DB_FILE" ]]; then
            print_info "Restoring SQLite database..."
            
            # Backup current database first
            if [[ -f "$DB_PATH" ]]; then
                cp "$DB_PATH" "${DB_PATH}.pre-rollback" 2>/dev/null || true
            fi
            
            # Create directory if needed
            mkdir -p "$(dirname "$DB_PATH")"
            
            # Restore database
            if cp "$SELECTED_BACKUP/$DB_FILE" "$DB_PATH"; then
                chown $SERVICE_USER:$SERVICE_USER "$DB_PATH"
                chmod 664 "$DB_PATH"
                print_success "SQLite database restored"
            else
                error_exit "Failed to restore SQLite database"
            fi
        else
            print_warning "SQLite database backup not found"
        fi
        
    elif [[ "$DATABASE_URL" =~ ^postgresql:// ]]; then
        # PostgreSQL restoration
        if [[ -f "$SELECTED_BACKUP/database.sql" ]]; then
            print_info "Restoring PostgreSQL database..."
            
            DB_NAME=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
            
            # Drop and recreate database
            sudo -u postgres psql << EOF >> "$LOG_FILE" 2>&1
DROP DATABASE IF EXISTS ${DB_NAME}_temp;
CREATE DATABASE ${DB_NAME}_temp;
EOF
            
            # Restore to temp database
            if sudo -u postgres psql ${DB_NAME}_temp < "$SELECTED_BACKUP/database.sql" >> "$LOG_FILE" 2>&1; then
                # Swap databases
                sudo -u postgres psql << EOF >> "$LOG_FILE" 2>&1
ALTER DATABASE $DB_NAME RENAME TO ${DB_NAME}_old;
ALTER DATABASE ${DB_NAME}_temp RENAME TO $DB_NAME;
DROP DATABASE ${DB_NAME}_old;
EOF
                print_success "PostgreSQL database restored"
            else
                print_error "Failed to restore PostgreSQL database"
            fi
        else
            print_warning "PostgreSQL database backup not found"
        fi
        
    elif [[ "$DATABASE_URL" =~ ^mysql:// ]]; then
        # MySQL restoration
        if [[ -f "$SELECTED_BACKUP/database.sql" ]]; then
            print_info "Restoring MySQL database..."
            
            DB_NAME=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
            DB_USER=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
            DB_PASS=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
            
            # Drop and recreate database
            mysql -u "$DB_USER" -p"$DB_PASS" << EOF >> "$LOG_FILE" 2>&1
DROP DATABASE IF EXISTS $DB_NAME;
CREATE DATABASE $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EOF
            
            # Restore database
            if mysql -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" < "$SELECTED_BACKUP/database.sql" >> "$LOG_FILE" 2>&1; then
                print_success "MySQL database restored"
            else
                print_error "Failed to restore MySQL database"
            fi
        else
            print_warning "MySQL database backup not found"
        fi
    else
        print_warning "Unknown database type, skipping database restore"
    fi
}

restore_configuration() {
    print_header "Restoring Configuration"
    
    if [[ -f "$SELECTED_BACKUP/.env" ]]; then
        print_info "Restoring .env configuration..."
        
        # Backup current .env
        if [[ -f "$INSTALL_DIR/.env" ]]; then
            cp "$INSTALL_DIR/.env" "$INSTALL_DIR/.env.pre-rollback" 2>/dev/null || true
        fi
        
        # Restore .env
        if cp "$SELECTED_BACKUP/.env" "$INSTALL_DIR/"; then
            chmod 600 "$INSTALL_DIR/.env"
            chown $SERVICE_USER:$SERVICE_USER "$INSTALL_DIR/.env"
            print_success "Configuration restored"
        else
            error_exit "Failed to restore configuration"
        fi
    else
        print_warning "No configuration backup found"
    fi
}

restore_uploads() {
    print_header "Restoring Upload Files"
    
    if [[ -d "$SELECTED_BACKUP/uploads" ]]; then
        print_info "Restoring uploaded files..."
        
        # Backup current uploads
        if [[ -d "$INSTALL_DIR/app/static/uploads" ]]; then
            mv "$INSTALL_DIR/app/static/uploads" "$INSTALL_DIR/app/static/uploads.pre-rollback" 2>/dev/null || true
        fi
        
        # Create directory
        mkdir -p "$INSTALL_DIR/app/static"
        
        # Restore uploads
        if cp -r "$SELECTED_BACKUP/uploads" "$INSTALL_DIR/app/static/"; then
            chown -R $SERVICE_USER:$SERVICE_USER "$INSTALL_DIR/app/static/uploads"
            print_success "Upload files restored"
        else
            print_warning "Failed to restore upload files"
        fi
    else
        print_info "No upload files to restore"
    fi
}

start_services() {
    print_header "Starting Services"
    
    # Start Celery worker
    print_info "Starting Celery worker..."
    if systemctl start kast-celery >> "$LOG_FILE" 2>&1; then
        print_success "Celery worker started"
    else
        print_warning "Failed to start Celery worker"
    fi
    
    # Wait for Celery to initialize
    sleep 2
    
    # Start web application
    print_info "Starting web application..."
    if systemctl start kast-web >> "$LOG_FILE" 2>&1; then
        print_success "Web application started"
    else
        error_exit "Failed to start web application"
    fi
    
    # Wait for services to initialize
    print_info "Waiting for services to initialize..."
    sleep 3
}

################################################################################
# Post-Rollback Validation
################################################################################

validate_rollback() {
    print_header "Post-Rollback Validation"
    
    local validation_failed=0
    
    # Check if services are running
    if systemctl is-active --quiet kast-web; then
        print_success "kast-web service is running"
    else
        print_error "kast-web service failed to start"
        validation_failed=1
    fi
    
    if systemctl is-active --quiet kast-celery; then
        print_success "kast-celery service is running"
    else
        print_error "kast-celery service failed to start"
        validation_failed=1
    fi
    
    # Test if application responds
    print_info "Testing application response..."
    sleep 2
    
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 2>/dev/null || echo "000")
    
    if [[ "$HTTP_CODE" == "200" ]] || [[ "$HTTP_CODE" == "302" ]]; then
        print_success "Application is responding (HTTP $HTTP_CODE)"
    else
        print_error "Application is not responding correctly (HTTP $HTTP_CODE)"
        validation_failed=1
    fi
    
    if [[ $validation_failed -eq 1 ]]; then
        print_error "Post-rollback validation failed"
        print_warning "Check logs: sudo journalctl -u kast-web -f"
        return 1
    fi
    
    print_success "All validation checks passed"
    return 0
}

################################################################################
# Main Rollback Flow
################################################################################

main() {
    # Print banner
    echo -e "${RED}${BOLD}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║                                                       ║"
    echo "║         KAST-Web Rollback Script v1.0                 ║"
    echo "║                                                       ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}\n"
    
    print_warning "This script will rollback KAST-Web to a previous backup"
    echo ""
    
    # Initialize log file
    mkdir -p "$(dirname "$LOG_FILE")"
    touch "$LOG_FILE"
    log "KAST-Web Rollback Started"
    log "Command: $0 $*"
    
    # Pre-rollback checks
    check_root
    
    # Select backup
    select_backup "$1"
    
    # Validate backup
    validate_backup
    
    # Confirm rollback
    echo ""
    print_warning "This will restore KAST-Web to the state in backup:"
    echo "  $(basename $SELECTED_BACKUP)"
    echo ""
    
    read -p "Are you sure you want to proceed with rollback? (y/N): " -r confirm
    
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        print_info "Rollback cancelled by user"
        exit 0
    fi
    
    # Execute rollback
    stop_services
    restore_git_state
    restore_database
    restore_configuration
    restore_uploads
    start_services
    
    # Validate rollback
    if validate_rollback; then
        # Generate report
        print_header "Rollback Complete"
        
        echo -e "${GREEN}${BOLD}"
        echo "╔═══════════════════════════════════════════════════════╗"
        echo "║                                                       ║"
        echo "║      KAST-Web Rollback Completed Successfully!        ║"
        echo "║                                                       ║"
        echo "╚═══════════════════════════════════════════════════════╝"
        echo -e "${NC}"
        
        echo -e "\n${CYAN}${BOLD}Rollback Summary:${NC}"
        echo -e "  Backup Used: ${GREEN}$(basename $SELECTED_BACKUP)${NC}"
        
        if [[ -f "$INSTALL_DIR/config.py" ]]; then
            CURRENT_VERSION=$(grep "^VERSION = " "$INSTALL_DIR/config.py" | cut -d"'" -f2)
            echo -e "  Current Version: ${GREEN}$CURRENT_VERSION${NC}"
        fi
        
        echo -e "\n${CYAN}${BOLD}Service Status:${NC}"
        systemctl is-active --quiet kast-web && echo -e "  Web Application: ${GREEN}RUNNING${NC}" || echo -e "  Web Application: ${RED}STOPPED${NC}"
        systemctl is-active --quiet kast-celery && echo -e "  Celery Worker:   ${GREEN}RUNNING${NC}" || echo -e "  Celery Worker:   ${RED}STOPPED${NC}"
        
        echo -e "\n${CYAN}${BOLD}Next Steps:${NC}"
        echo "  • Test the application in your browser"
        echo "  • Verify functionality has been restored"
        echo "  • Check logs: sudo journalctl -u kast-web -f"
        
        echo -e "\n${GREEN}Rollback log saved to: $LOG_FILE${NC}\n"
        
        log "KAST-Web Rollback Completed Successfully"
    else
        print_error "Rollback validation failed"
        print_warning "Manual intervention may be required"
        print_warning "Check logs: sudo journalctl -u kast-web -xe"
        exit 1
    fi
}

# Run main function
main "$@"
