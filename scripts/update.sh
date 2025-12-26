#!/bin/bash

################################################################################
# KAST-Web Update Script
# Version: 2.0.0
# Description: Update script for production KAST-Web deployments
#              Supports two-directory model: source → installation
# Usage: sudo ./scripts/update.sh [options]
################################################################################

set -e  # Exit on error
set -o pipefail  # Catch errors in pipes

################################################################################
# Configuration Variables
################################################################################

# Detect source directory (where this script is run from)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(dirname "$SCRIPT_DIR")"  # Parent of scripts/ directory

# Installation directory (where the app runs)
INSTALL_DIR="/opt/kast-web"  # Default, can be overridden with --install-dir

# Other paths (relative to installation)
BACKUP_BASE_DIR=""  # Will be set based on INSTALL_DIR
LOG_FILE="/var/log/kast-web/update.log"

# Update modes
UPDATE_MODE="quick"  # quick or full
DRY_RUN="no"
FORCE_UPDATE="no"
SKIP_BACKUP="no"
BACKUP_DIR=""
ROLLBACK_ON_FAILURE="yes"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
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
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_header() {
    echo -e "\n${CYAN}${BOLD}═══════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}${BOLD}  $1${NC}"
    echo -e "${CYAN}${BOLD}═══════════════════════════════════════════════════════${NC}\n"
}

# Error handler
error_exit() {
    print_error "$1"
    log "ERROR: $1"
    if [[ "$ROLLBACK_ON_FAILURE" == "yes" && -n "$BACKUP_DIR" && -d "$BACKUP_DIR" ]]; then
        print_warning "Attempting automatic rollback..."
        perform_rollback
    fi
    log "Update failed. Check $LOG_FILE for details."
    exit 1
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error_exit "This script must be run as root or with sudo"
    fi
}

################################################################################
# Command-line Argument Parsing
################################################################################

show_help() {
    cat << EOF
KAST-Web Update Script v2.0

Usage: sudo ./scripts/update.sh [options]

This script updates a KAST-Web installation from a source directory.
Run this script from your source directory (e.g., ~/kast-web).

Update Modes:
  (default)          Quick update - copy files and restart services (10-15s downtime)
  --full             Full update - includes dependencies and migrations (30-60s downtime)

Options:
  --install-dir PATH Specify installation directory (default: /opt/kast-web)
  --dry-run          Show what would be done without making changes
  --force            Skip safety checks and force update
  --skip-backup      Skip backup creation (NOT RECOMMENDED)
  --no-rollback      Disable automatic rollback on failure
  --help, -h         Show this help message

Examples:
  # Quick update to default location
  cd ~/kast-web
  sudo ./scripts/update.sh

  # Full update with custom installation directory
  cd ~/kast-web
  sudo ./scripts/update.sh --full --install-dir /opt/kast-web

  # Preview changes
  sudo ./scripts/update.sh --dry-run

Workflow:
  1. Pull/download updates to source directory (~/kast-web)
  2. Run this script from source directory
  3. Script copies updates to installation directory (/opt/kast-web)
  4. Services restarted, migrations run (if --full)

EOF
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --install-dir)
                INSTALL_DIR="$2"
                shift 2
                ;;
            --full)
                UPDATE_MODE="full"
                shift
                ;;
            --dry-run)
                DRY_RUN="yes"
                shift
                ;;
            --force)
                FORCE_UPDATE="yes"
                shift
                ;;
            --skip-backup)
                SKIP_BACKUP="yes"
                shift
                ;;
            --no-rollback)
                ROLLBACK_ON_FAILURE="no"
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Set backup directory based on installation directory
    BACKUP_BASE_DIR="${INSTALL_DIR}-backup"
}

################################################################################
# Directory Detection & Validation
################################################################################

detect_installation_dir() {
    print_header "Directory Detection"
    
    print_info "Source directory: $SOURCE_DIR"
    
    # Check if installation directory exists
    if [[ ! -d "$INSTALL_DIR" ]]; then
        print_error "Installation directory not found: $INSTALL_DIR"
        echo ""
        read -p "Enter installation directory path: " -r user_install_dir
        
        if [[ -d "$user_install_dir" ]]; then
            INSTALL_DIR="$user_install_dir"
            BACKUP_BASE_DIR="${INSTALL_DIR}-backup"
            print_success "Using installation directory: $INSTALL_DIR"
        else
            error_exit "Invalid installation directory: $user_install_dir"
        fi
    else
        print_success "Installation directory: $INSTALL_DIR"
    fi
}

validate_source_directory() {
    print_header "Source Directory Validation"
    
    # Check we're in a valid KAST-Web source directory
    if [[ ! -f "$SOURCE_DIR/config.py" ]]; then
        error_exit "Not a valid KAST-Web source directory (config.py not found)"
    fi
    
    print_success "Valid KAST-Web source directory"
    
    # Check for scripts directory
    if [[ ! -d "$SOURCE_DIR/scripts" ]]; then
        error_exit "Scripts directory not found in source"
    fi
    
    print_success "Scripts directory found"
    
    # Get source version
    SOURCE_VERSION=$(grep "^VERSION = " "$SOURCE_DIR/config.py" | cut -d"'" -f2 || echo "unknown")
    print_info "Source version: $SOURCE_VERSION"
}

validate_installation_directory() {
    print_header "Installation Directory Validation"
    
    # Check installation has required structure
    if [[ ! -f "$INSTALL_DIR/config.py" ]]; then
        error_exit "Installation directory invalid (config.py not found)"
    fi
    
    print_success "Valid KAST-Web installation directory"
    
    # Check virtual environment exists
    if [[ ! -d "$INSTALL_DIR/venv" ]]; then
        error_exit "Virtual environment not found at $INSTALL_DIR/venv"
    fi
    
    print_success "Virtual environment found"
    
    # Check services exist
    if [[ ! -f /etc/systemd/system/kast-web.service ]]; then
        error_exit "kast-web service not found at /etc/systemd/system/kast-web.service"
    fi
    
    if [[ ! -f /etc/systemd/system/kast-celery.service ]]; then
        error_exit "kast-celery service not found at /etc/systemd/system/kast-celery.service"
    fi
    
    print_success "Systemd services verified"
    
    # Get current version
    CURRENT_VERSION=$(grep "^VERSION = " "$INSTALL_DIR/config.py" | cut -d"'" -f2 || echo "unknown")
    print_info "Current installation version: $CURRENT_VERSION"
    
    # Check disk space (need at least 1GB free)
    AVAILABLE_SPACE=$(df "$INSTALL_DIR" | tail -1 | awk '{print $4}')
    REQUIRED_SPACE=1048576  # 1GB in KB
    
    if [[ $AVAILABLE_SPACE -lt $REQUIRED_SPACE ]]; then
        error_exit "Insufficient disk space. Required: 1GB, Available: $((AVAILABLE_SPACE/1024))MB"
    fi
    
    print_success "Sufficient disk space: $((AVAILABLE_SPACE/1024/1024))GB available"
}

check_version_difference() {
    print_header "Version Check"
    
    print_info "Source version:      $SOURCE_VERSION"
    print_info "Installation version: $CURRENT_VERSION"
    
    if [[ "$SOURCE_VERSION" == "$CURRENT_VERSION" ]]; then
        print_warning "Source and installation are same version"
        if [[ "$FORCE_UPDATE" != "yes" && "$DRY_RUN" != "yes" ]]; then
            echo ""
            read -p "Continue with update anyway? (y/N): " -r response
            if [[ ! "$response" =~ ^[Yy]$ ]]; then
                print_info "Update cancelled"
                exit 0
            fi
        fi
    else
        print_success "Version difference detected - update available"
    fi
}

check_service_status() {
    print_header "Service Status Check"
    
    # Check if services are running
    if systemctl is-active --quiet kast-web; then
        print_success "kast-web service is running"
    else
        print_warning "kast-web service is not running"
    fi
    
    if systemctl is-active --quiet kast-celery; then
        print_success "kast-celery service is running"
    else
        print_warning "kast-celery service is not running"
    fi
    
    if systemctl is-active --quiet redis-server; then
        print_success "Redis is running"
    else
        print_warning "Redis is not running"
    fi
}

################################################################################
# Backup Creation
################################################################################

create_backup() {
    if [[ "$SKIP_BACKUP" == "yes" ]]; then
        print_warning "Skipping backup creation (--skip-backup flag)"
        return 0
    fi
    
    print_header "Creating Backup"
    
    BACKUP_DIR="${BACKUP_BASE_DIR}-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    print_info "Backup location: $BACKUP_DIR"
    
    # Save version information
    cat > "$BACKUP_DIR/backup-info.txt" << EOF
Backup created: $(date)
Update type: $UPDATE_MODE
Source directory: $SOURCE_DIR
Installation directory: $INSTALL_DIR
Current version: $CURRENT_VERSION
Source version: $SOURCE_VERSION
EOF
    
    # Backup key files from installation
    print_info "Backing up configuration and data..."
    
    # Backup .env
    if [[ -f "$INSTALL_DIR/.env" ]]; then
        cp "$INSTALL_DIR/.env" "$BACKUP_DIR/" 2>/dev/null || true
        print_success "Configuration backed up"
    fi
    
    # Backup database
    if [[ -f "$INSTALL_DIR/.env" ]]; then
        source "$INSTALL_DIR/.env"
        
        if [[ -n "$DATABASE_URL" ]]; then
            if [[ "$DATABASE_URL" =~ ^sqlite:/// ]]; then
                DB_PATH="${DATABASE_URL#sqlite:///}"
                # Handle both absolute and relative paths
                if [[ "$DB_PATH" != /* ]]; then
                    DB_PATH="$INSTALL_DIR/$DB_PATH"
                fi
                
                if [[ -f "$DB_PATH" ]]; then
                    mkdir -p "$BACKUP_DIR/$(dirname "$DB_PATH")"
                    cp "$DB_PATH" "$BACKUP_DIR/$(basename "$DB_PATH")" 2>/dev/null || true
                    print_success "SQLite database backed up"
                fi
            fi
        fi
    fi
    
    # Backup uploads
    if [[ -d "$INSTALL_DIR/app/static/uploads" ]]; then
        cp -r "$INSTALL_DIR/app/static/uploads" "$BACKUP_DIR/" 2>/dev/null || true
        print_success "Upload files backed up"
    fi
    
    # Backup instance directory if exists
    if [[ -d "$INSTALL_DIR/instance" ]]; then
        cp -r "$INSTALL_DIR/instance" "$BACKUP_DIR/" 2>/dev/null || true
        print_success "Instance directory backed up"
    fi
    
    print_success "Backup completed: $BACKUP_DIR"
    log "Backup created at $BACKUP_DIR"
    
    # Cleanup old backups (keep last 5)
    cleanup_old_backups
}

cleanup_old_backups() {
    print_info "Cleaning up old backups (keeping last 5)..."
    
    # Count backups
    BACKUP_COUNT=$(ls -d ${BACKUP_BASE_DIR}-* 2>/dev/null | wc -l)
    
    if [[ $BACKUP_COUNT -gt 5 ]]; then
        # Remove oldest backups
        ls -dt ${BACKUP_BASE_DIR}-* | tail -n +6 | while read old_backup; do
            rm -rf "$old_backup"
            print_info "Removed old backup: $(basename $old_backup)"
        done
    fi
}

################################################################################
# File Copying
################################################################################

copy_files() {
    print_header "Copying Files from Source to Installation"
    
    if [[ "$DRY_RUN" == "yes" ]]; then
        print_info "[DRY RUN] Would copy updated files to installation"
        return 0
    fi
    
    # Stop services before copying
    print_info "Stopping services..."
    systemctl stop kast-web kast-celery 2>/dev/null || true
    
    # Copy application files (exclude certain directories)
    print_info "Copying application files..."
    
    rsync -av --delete \
        --exclude='.git' \
        --exclude='.gitignore' \
        --exclude='venv/' \
        --exclude='.env' \
        --exclude='instance/' \
        --exclude='app/static/uploads/' \
        --exclude='*.pyc' \
        --exclude='__pycache__' \
        --exclude='.pytest_cache' \
        --exclude='*.log' \
        "$SOURCE_DIR/" "$INSTALL_DIR/" >> "$LOG_FILE" 2>&1 || error_exit "Failed to copy files"
    
    print_success "Files copied successfully"
    
    # Ensure correct ownership
    print_info "Setting file ownership..."
    chown -R www-data:www-data "$INSTALL_DIR" 2>/dev/null || true
    
    # Ensure scripts are executable
    chmod +x "$INSTALL_DIR/scripts"/*.sh 2>/dev/null || true
    
    print_success "File permissions updated"
}

################################################################################
# Dependencies & Migrations
################################################################################

update_dependencies() {
    if [[ "$UPDATE_MODE" != "full" ]]; then
        print_info "Skipping dependency update (use --full for dependency updates)"
        return 0
    fi
    
    print_header "Updating Python Dependencies"
    
    cd "$INSTALL_DIR" || error_exit "Failed to change to installation directory"
    
    if [[ "$DRY_RUN" == "yes" ]]; then
        print_info "[DRY RUN] Would update pip and install requirements"
        return 0
    fi
    
    # Activate installation venv
    source "$INSTALL_DIR/venv/bin/activate" || error_exit "Failed to activate virtual environment"
    
    print_info "Upgrading pip..."
    pip install --upgrade pip >> "$LOG_FILE" 2>&1 || print_warning "Failed to upgrade pip (continuing)"
    
    print_info "Installing/updating dependencies..."
    if [[ -f "$INSTALL_DIR/requirements-production.txt" ]]; then
        if pip install -r "$INSTALL_DIR/requirements-production.txt" >> "$LOG_FILE" 2>&1; then
            print_success "Dependencies updated successfully"
        else
            error_exit "Failed to update dependencies. Check $LOG_FILE"
        fi
    elif [[ -f "$INSTALL_DIR/requirements.txt" ]]; then
        if pip install -r "$INSTALL_DIR/requirements.txt" >> "$LOG_FILE" 2>&1; then
            print_success "Dependencies updated successfully"
        else
            error_exit "Failed to update dependencies. Check $LOG_FILE"
        fi
    else
        print_warning "No requirements file found"
    fi
    
    deactivate 2>/dev/null || true
}

run_migrations() {
    if [[ "$UPDATE_MODE" != "full" ]]; then
        print_info "Skipping migrations (use --full to run migrations)"
        return 0
    fi
    
    print_header "Running Database Migrations"
    
    cd "$INSTALL_DIR" || error_exit "Failed to change to installation directory"
    
    if [[ "$DRY_RUN" == "yes" ]]; then
        print_info "[DRY RUN] Would run migration scripts from utils/"
        if [[ -d "$INSTALL_DIR/utils" ]]; then
            ls "$INSTALL_DIR"/utils/migrate*.py 2>/dev/null | while read migration; do
                print_info "[DRY RUN] Would run: $(basename $migration)"
            done
        fi
        return 0
    fi
    
    # Activate installation venv
    source "$INSTALL_DIR/venv/bin/activate" || error_exit "Failed to activate virtual environment"
    
    # Load environment variables
    set -a
    source "$INSTALL_DIR/.env" 2>/dev/null || true
    set +a
    
    export PYTHONPATH="$INSTALL_DIR"
    
    # Run migration scripts if they exist
    if [[ -d "$INSTALL_DIR/utils" ]]; then
        # Set environment variable for non-interactive mode
        export NON_INTERACTIVE=1
        
        MIGRATION_COUNT=0
        for migration in "$INSTALL_DIR"/utils/migrate*.py; do
            if [[ -f "$migration" ]]; then
                print_info "Running migration: $(basename "$migration")"
                # Pass --non-interactive flag to all migration scripts
                if python3 "$migration" --non-interactive >> "$LOG_FILE" 2>&1; then
                    print_success "Migration completed: $(basename "$migration")"
                    ((MIGRATION_COUNT++))
                else
                    print_warning "Migration had issues: $(basename "$migration") (continuing)"
                fi
            fi
        done
        
        # Unset the environment variable
        unset NON_INTERACTIVE
        
        if [[ $MIGRATION_COUNT -gt 0 ]]; then
            print_success "Ran $MIGRATION_COUNT migration(s)"
        else
            print_info "No migrations to run"
        fi
    else
        print_info "No migrations directory found"
    fi
    
    deactivate 2>/dev/null || true
}

################################################################################
# Service Management
################################################################################

restart_services() {
    print_header "Restarting Services"
    
    if [[ "$DRY_RUN" == "yes" ]]; then
        print_info "[DRY RUN] Would restart kast-celery and kast-web services"
        return 0
    fi
    
    # Restart Celery worker first
    print_info "Restarting Celery worker..."
    if systemctl restart kast-celery >> "$LOG_FILE" 2>&1; then
        print_success "Celery worker restarted"
    else
        print_warning "Failed to restart Celery worker"
    fi
    
    # Small delay to let Celery settle
    sleep 2
    
    # Restart web application
    print_info "Restarting web application..."
    if systemctl restart kast-web >> "$LOG_FILE" 2>&1; then
        print_success "Web application restarted"
    else
        error_exit "Failed to restart web application"
    fi
    
    # Wait for services to start
    print_info "Waiting for services to initialize..."
    sleep 3
}

################################################################################
# Post-Update Validation
################################################################################

validate_update() {
    print_header "Post-Update Validation"
    
    if [[ "$DRY_RUN" == "yes" ]]; then
        print_info "[DRY RUN] Would validate services and application"
        return 0
    fi
    
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
    
    # Check new version
    NEW_VERSION=$(grep "^VERSION = " "$INSTALL_DIR/config.py" | cut -d"'" -f2)
    print_info "Updated to version: $NEW_VERSION"
    
    if [[ $validation_failed -eq 1 ]]; then
        error_exit "Post-update validation failed"
    fi
    
    print_success "All validation checks passed"
}

################################################################################
# Rollback Functions
################################################################################

perform_rollback() {
    print_header "Rolling Back Update"
    
    if [[ ! -d "$BACKUP_DIR" ]]; then
        print_error "Backup directory not found: $BACKUP_DIR"
        return 1
    fi
    
    print_warning "Restoring from backup: $BACKUP_DIR"
    
    # Stop services
    systemctl stop kast-web kast-celery 2>/dev/null || true
    
    # Restore .env
    if [[ -f "$BACKUP_DIR/.env" ]]; then
        cp "$BACKUP_DIR/.env" "$INSTALL_DIR/" 2>/dev/null || true
        print_success "Configuration restored"
    fi
    
    # Restore database
    if [[ -f "$INSTALL_DIR/.env" ]]; then
        source "$INSTALL_DIR/.env"
        
        if [[ -n "$DATABASE_URL" && "$DATABASE_URL" =~ ^sqlite:/// ]]; then
            DB_PATH="${DATABASE_URL#sqlite:///}"
            if [[ "$DB_PATH" != /* ]]; then
                DB_PATH="$INSTALL_DIR/$DB_PATH"
            fi
            
            DB_BACKUP=$(find "$BACKUP_DIR" -name "*.db" -type f | head -1)
            if [[ -n "$DB_BACKUP" && -f "$DB_BACKUP" ]]; then
                cp "$DB_BACKUP" "$DB_PATH" 2>/dev/null || true
                print_success "Database restored"
            fi
        fi
    fi
    
    # Restore uploads
    if [[ -d "$BACKUP_DIR/uploads" ]]; then
        rm -rf "$INSTALL_DIR/app/static/uploads" 2>/dev/null || true
        cp -r "$BACKUP_DIR/uploads" "$INSTALL_DIR/app/static/uploads" 2>/dev/null || true
        print_success "Uploads restored"
    fi
    
    # Restore instance
    if [[ -d "$BACKUP_DIR/instance" ]]; then
        rm -rf "$INSTALL_DIR/instance" 2>/dev/null || true
        cp -r "$BACKUP_DIR/instance" "$INSTALL_DIR/instance" 2>/dev/null || true
        print_success "Instance directory restored"
    fi
    
    # Restart services
    systemctl start kast-celery >> "$LOG_FILE" 2>&1 || true
    sleep 2
    systemctl start kast-web >> "$LOG_FILE" 2>&1 || true
    sleep 3
    
    # Verify rollback
    if systemctl is-active --quiet kast-web; then
        print_success "Services restarted after rollback"
    else
        print_error "Services failed to start after rollback"
        print_error "Manual intervention required!"
        return 1
    fi
    
    print_success "Rollback completed"
    log "Rollback successful from $BACKUP_DIR"
}

################################################################################
# Main Update Flow
################################################################################

main() {
    # Parse command-line arguments
    parse_arguments "$@"
    
    # Print banner
    echo -e "${CYAN}${BOLD}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║                                                       ║"
    echo "║          KAST-Web Update Script v2.0                  ║"
    echo "║                                                       ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}\n"
    
    if [[ "$DRY_RUN" == "yes" ]]; then
        print_warning "DRY RUN MODE - No changes will be made"
    fi
    
    # Initialize log file
    mkdir -p "$(dirname "$LOG_FILE")"
    touch "$LOG_FILE"
    # Set proper ownership for log directory and file
    chown -R www-data:www-data "$(dirname "$LOG_FILE")"
    chmod 755 "$(dirname "$LOG_FILE")"
    chmod 644 "$LOG_FILE"
    log "KAST-Web Update Started (v2.0)"
    log "Update mode: $UPDATE_MODE"
    log "Source directory: $SOURCE_DIR"
    log "Installation directory: $INSTALL_DIR"
    log "Command: $0 $*"
    
    # Pre-update checks
    check_root
    detect_installation_dir
    validate_source_directory
    validate_installation_directory
    check_version_difference
    check_service_status
    
    # Show update summary
    print_header "Update Summary"
    echo -e "${CYAN}${BOLD}Update Configuration:${NC}"
    echo -e "  Update Mode:          ${GREEN}$UPDATE_MODE${NC}"
    echo -e "  Source Directory:     ${GREEN}$SOURCE_DIR${NC}"
    echo -e "  Installation Directory: ${GREEN}$INSTALL_DIR${NC}"
    echo -e "  Source Version:       ${GREEN}$SOURCE_VERSION${NC}"
    echo -e "  Current Version:      ${GREEN}$CURRENT_VERSION${NC}"
    echo -e "  Create Backup:        ${GREEN}$([ "$SKIP_BACKUP" == "yes" ] && echo "no" || echo "yes")${NC}"
    echo -e "  Auto Rollback:        ${GREEN}$([ "$ROLLBACK_ON_FAILURE" == "yes" ] && echo "yes" || echo "no")${NC}"
    echo ""
    
    if [[ "$UPDATE_MODE" == "quick" ]]; then
        echo -e "${CYAN}Quick Update will:${NC}"
        echo "  • Copy updated files to installation"
        echo "  • Restart services (~10-15 seconds downtime)"
    else
        echo -e "${CYAN}Full Update will:${NC}"
        echo "  • Copy updated files to installation"
        echo "  • Update Python dependencies"
        echo "  • Run database migrations"
        echo "  • Restart services (~30-60 seconds downtime)"
    fi
    
    if [[ "$DRY_RUN" != "yes" ]]; then
        echo ""
        read -p "Proceed with update? (Y/n): " -r proceed_choice
        
        if [[ "$proceed_choice" =~ ^[Nn]$ ]]; then
            print_info "Update cancelled by user"
            exit 0
        fi
    fi
    
    # Execute update
    create_backup
    copy_files
    update_dependencies
    run_migrations
    restart_services
    validate_update
    
    # Generate report
    print_header "Update Complete"
    
    echo -e "${GREEN}${BOLD}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║                                                       ║"
    echo "║      KAST-Web Update Completed Successfully!         ║"
    echo "║                                                       ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "\n${CYAN}${BOLD}Update Summary:${NC}"
    echo -e "  Previous Version:     ${GREEN}$CURRENT_VERSION${NC}"
    echo -e "  Current Version:      ${GREEN}$NEW_VERSION${NC}"
    echo -e "  Source Directory:     ${GREEN}$SOURCE_DIR${NC}"
    echo -e "  Installation Directory: ${GREEN}$INSTALL_DIR${NC}"
    
    if [[ "$SKIP_BACKUP" != "yes" ]]; then
        echo -e "  Backup Location:      ${GREEN}$BACKUP_DIR${NC}"
    fi
    
    echo -e "\n${CYAN}${BOLD}Service Status:${NC}"
    systemctl is-active --quiet kast-web && echo -e "  Web Application: ${GREEN}RUNNING${NC}" || echo -e "  Web Application: ${RED}STOPPED${NC}"
    systemctl is-active --quiet kast-celery && echo -e "  Celery Worker:   ${GREEN}RUNNING${NC}" || echo -e "  Celery Worker:   ${RED}STOPPED${NC}"
    
    echo -e "\n${CYAN}${BOLD}Next Steps:${NC}"
    echo "  • Test the application in your browser"
    echo "  • Check logs: sudo journalctl -u kast-web -f"
    echo "  • Monitor for any issues"
    
    if [[ "$SKIP_BACKUP" != "yes" ]]; then
        echo "  • Rollback if needed: sudo $INSTALL_DIR/scripts/rollback.sh"
    fi
    
    echo -e "\n${GREEN}Update log saved to: $LOG_FILE${NC}\n"
    
    log "KAST-Web Update Completed Successfully"
    log "Updated from $CURRENT_VERSION to $NEW_VERSION"
}

# Run main function
main "$@"
