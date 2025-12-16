#!/bin/bash

################################################################################
# KAST-Web Update Script
# Version: 1.0.0
# Description: Smart update script for production KAST-Web deployments
# Usage: sudo ./scripts/update.sh [options]
################################################################################

set -e  # Exit on error
set -o pipefail  # Catch errors in pipes

################################################################################
# Configuration Variables
################################################################################

# Detect installation directory from script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$(dirname "$SCRIPT_DIR")"  # Parent of scripts/ directory
BACKUP_BASE_DIR="${INSTALL_DIR}-backup"
LOG_FILE="/var/log/kast-web/update.log"
SERVICE_USER="www-data"
VENV_DIR="$INSTALL_DIR/venv"

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
KAST-Web Update Script

Usage: sudo ./scripts/update.sh [options]

Update Modes:
  (default)          Quick update - pull code and restart services (10-15s downtime)
  --full             Full update - includes dependency updates and migrations (30-60s downtime)

Options:
  --dry-run          Show what would be done without making changes
  --force            Skip safety checks and force update
  --skip-backup      Skip backup creation (NOT RECOMMENDED)
  --no-rollback      Disable automatic rollback on failure
  --help, -h         Show this help message

Examples:
  # Quick update (CSS, templates, code changes)
  sudo ./scripts/update.sh

  # Full update (new dependencies, database migrations)
  sudo ./scripts/update.sh --full

  # Preview changes without applying
  sudo ./scripts/update.sh --dry-run

  # Force update even with uncommitted changes
  sudo ./scripts/update.sh --force

EOF
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
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
}

################################################################################
# Pre-Update Validation
################################################################################

validate_environment() {
    print_header "Environment Validation"
    
    # Check we're in the correct directory
    if [[ ! -f "$INSTALL_DIR/config.py" ]]; then
        error_exit "Not in KAST-Web installation directory. Expected: $INSTALL_DIR"
    fi
    
    print_success "Installation directory verified"
    
    # Check virtual environment exists
    if [[ ! -d "$VENV_DIR" ]]; then
        error_exit "Virtual environment not found at $VENV_DIR"
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
    
    # Check disk space (need at least 1GB free)
    AVAILABLE_SPACE=$(df /opt | tail -1 | awk '{print $4}')
    REQUIRED_SPACE=1048576  # 1GB in KB
    
    if [[ $AVAILABLE_SPACE -lt $REQUIRED_SPACE ]]; then
        error_exit "Insufficient disk space. Required: 1GB, Available: $((AVAILABLE_SPACE/1024))MB"
    fi
    
    print_success "Sufficient disk space available: $((AVAILABLE_SPACE/1024/1024))GB"
}

check_git_status() {
    print_header "Git Repository Status"
    
    # Check if we're in a git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        error_exit "Not a git repository. This update script requires git."
    fi
    
    print_success "Git repository detected"
    
    # Get current branch
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    print_info "Current branch: $CURRENT_BRANCH"
    
    # Get current commit
    CURRENT_COMMIT=$(git rev-parse HEAD)
    CURRENT_COMMIT_SHORT=$(git rev-parse --short HEAD)
    print_info "Current commit: $CURRENT_COMMIT_SHORT"
    
    # Check for uncommitted changes
    if [[ -n $(git status --porcelain) ]]; then
        print_warning "Uncommitted changes detected:"
        git status --short | while read line; do
            echo "    $line"
        done
        
        if [[ "$FORCE_UPDATE" != "yes" && "$DRY_RUN" != "yes" ]]; then
            echo ""
            read -p "Continue with update despite uncommitted changes? (y/N): " -r response
            if [[ ! "$response" =~ ^[Yy]$ ]]; then
                print_info "Update cancelled"
                exit 0
            fi
        fi
    else
        print_success "Working directory clean"
    fi
    
    # Check for updates
    print_info "Fetching updates from remote..."
    git fetch origin 2>&1 | tee -a "$LOG_FILE"
    
    LOCAL=$(git rev-parse @)
    REMOTE=$(git rev-parse @{u} 2>/dev/null || echo "")
    
    if [[ -z "$REMOTE" ]]; then
        print_warning "No upstream branch configured"
    elif [[ "$LOCAL" == "$REMOTE" ]]; then
        print_info "Already up to date with remote"
        if [[ "$FORCE_UPDATE" != "yes" && "$DRY_RUN" != "yes" ]]; then
            echo ""
            read -p "No updates available. Continue anyway? (y/N): " -r response
            if [[ ! "$response" =~ ^[Yy]$ ]]; then
                print_info "Update cancelled"
                exit 0
            fi
        fi
    else
        AHEAD=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo "0")
        BEHIND=$(git rev-list --count HEAD..@{u} 2>/dev/null || echo "0")
        
        if [[ "$BEHIND" -gt 0 ]]; then
            print_success "Updates available: $BEHIND commit(s) behind remote"
        fi
        
        if [[ "$AHEAD" -gt 0 ]]; then
            print_warning "Local repository is $AHEAD commit(s) ahead of remote"
        fi
    fi
}

get_version_info() {
    # Extract current version from config.py
    if [[ -f "$INSTALL_DIR/config.py" ]]; then
        CURRENT_VERSION=$(grep "^VERSION = " "$INSTALL_DIR/config.py" | cut -d"'" -f2)
    else
        CURRENT_VERSION="unknown"
    fi
    
    # Get incoming version (after fetch)
    INCOMING_VERSION=$(git show origin/$(git rev-parse --abbrev-ref HEAD):config.py 2>/dev/null | grep "^VERSION = " | cut -d"'" -f2 || echo "unknown")
    
    print_info "Current version: $CURRENT_VERSION"
    print_info "Incoming version: $INCOMING_VERSION"
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
Current version: $CURRENT_VERSION
Current commit: $CURRENT_COMMIT
Installation directory: $INSTALL_DIR
EOF
    
    # Backup database
    if [[ -f "$INSTALL_DIR/.env" ]]; then
        source "$INSTALL_DIR/.env"
        
        if [[ "$DATABASE_URL" =~ ^sqlite:/// ]]; then
            DB_PATH="${DATABASE_URL#sqlite:///}"
            if [[ -f "$DB_PATH" ]]; then
                cp "$DB_PATH" "$BACKUP_DIR/" 2>/dev/null || true
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
    if [[ -f "$INSTALL_DIR/.env" ]]; then
        cp "$INSTALL_DIR/.env" "$BACKUP_DIR/" 2>/dev/null || true
        print_success "Configuration backed up"
    fi
    
    # Backup uploads
    if [[ -d "$INSTALL_DIR/app/static/uploads" ]]; then
        cp -r "$INSTALL_DIR/app/static/uploads" "$BACKUP_DIR/" 2>/dev/null || true
        print_success "Upload files backed up"
    fi
    
    # Save git commit hash
    echo "$CURRENT_COMMIT" > "$BACKUP_DIR/git-commit.txt"
    
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
# Update Execution
################################################################################

perform_git_pull() {
    print_header "Pulling Updates from Git"
    
    if [[ "$DRY_RUN" == "yes" ]]; then
        print_info "[DRY RUN] Would execute: git pull origin $CURRENT_BRANCH"
        print_info "[DRY RUN] Changes that would be pulled:"
        git log --oneline HEAD..@{u} 2>/dev/null | head -10
        return 0
    fi
    
    print_info "Executing: git pull origin $CURRENT_BRANCH"
    
    if git pull origin "$CURRENT_BRANCH" >> "$LOG_FILE" 2>&1; then
        NEW_COMMIT=$(git rev-parse --short HEAD)
        print_success "Git pull completed. New commit: $NEW_COMMIT"
        
        # Show what changed
        if [[ "$CURRENT_COMMIT_SHORT" != "$NEW_COMMIT" ]]; then
            print_info "Changes pulled:"
            git log --oneline "$CURRENT_COMMIT_SHORT..$NEW_COMMIT" | while read line; do
                echo "    $line"
            done
        fi
    else
        error_exit "Git pull failed. Check $LOG_FILE for details."
    fi
}

update_dependencies() {
    if [[ "$UPDATE_MODE" != "full" ]]; then
        print_info "Skipping dependency update (use --full for dependency updates)"
        return 0
    fi
    
    print_header "Updating Python Dependencies"
    
    cd "$INSTALL_DIR" || error_exit "Failed to change to installation directory"
    source "$VENV_DIR/bin/activate" || error_exit "Failed to activate virtual environment"
    
    if [[ "$DRY_RUN" == "yes" ]]; then
        print_info "[DRY RUN] Would update pip and install requirements"
        return 0
    fi
    
    print_info "Upgrading pip..."
    if ! pip install --upgrade pip >> "$LOG_FILE" 2>&1; then
        print_warning "Failed to upgrade pip (continuing anyway)"
    fi
    
    print_info "Installing/updating dependencies..."
    if [[ -f "$INSTALL_DIR/requirements-production.txt" ]]; then
        if pip install -r "$INSTALL_DIR/requirements-production.txt" >> "$LOG_FILE" 2>&1; then
            print_success "Dependencies updated successfully"
        else
            error_exit "Failed to update dependencies. Check $LOG_FILE for details."
        fi
    elif [[ -f "$INSTALL_DIR/requirements.txt" ]]; then
        if pip install -r "$INSTALL_DIR/requirements.txt" >> "$LOG_FILE" 2>&1; then
            print_success "Dependencies updated successfully"
        else
            error_exit "Failed to update dependencies. Check $LOG_FILE for details."
        fi
    else
        print_warning "No requirements file found"
    fi
}

run_migrations() {
    if [[ "$UPDATE_MODE" != "full" ]]; then
        print_info "Skipping migrations (use --full to run migrations)"
        return 0
    fi
    
    print_header "Running Database Migrations"
    
    cd "$INSTALL_DIR" || error_exit "Failed to change to installation directory"
    source "$VENV_DIR/bin/activate" || error_exit "Failed to activate virtual environment"
    
    if [[ "$DRY_RUN" == "yes" ]]; then
        print_info "[DRY RUN] Would run migration scripts from utils/"
        if [[ -d "$INSTALL_DIR/utils" ]]; then
            ls "$INSTALL_DIR"/utils/migrate*.py 2>/dev/null | while read migration; do
                print_info "[DRY RUN] Would run: $(basename $migration)"
            done
        fi
        return 0
    fi
    
    # Load environment variables
    set -a
    source "$INSTALL_DIR/.env" 2>/dev/null || true
    set +a
    
    export PYTHONPATH="$INSTALL_DIR"
    
    # Run migration scripts if they exist
    if [[ -d "$INSTALL_DIR/utils" ]]; then
        MIGRATION_COUNT=0
        for migration in "$INSTALL_DIR"/utils/migrate*.py; do
            if [[ -f "$migration" ]]; then
                print_info "Running migration: $(basename "$migration")"
                if python3 "$migration" >> "$LOG_FILE" 2>&1; then
                    print_success "Migration completed: $(basename "$migration")"
                    ((MIGRATION_COUNT++))
                else
                    print_warning "Migration had issues: $(basename "$migration") (continuing)"
                fi
            fi
        done
        
        if [[ $MIGRATION_COUNT -gt 0 ]]; then
            print_success "Ran $MIGRATION_COUNT migration(s)"
        else
            print_info "No migrations to run"
        fi
    else
        print_info "No migrations directory found"
    fi
}

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
    cd "$INSTALL_DIR"
    source "$VENV_DIR/bin/activate"
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
    
    # Restore git commit
    if [[ -f "$BACKUP_DIR/git-commit.txt" ]]; then
        RESTORE_COMMIT=$(cat "$BACKUP_DIR/git-commit.txt")
        print_info "Restoring git commit: $RESTORE_COMMIT"
        git reset --hard "$RESTORE_COMMIT" >> "$LOG_FILE" 2>&1 || print_warning "Git reset failed"
    fi
    
    # Restore database
    if [[ -f "$INSTALL_DIR/.env" ]]; then
        source "$INSTALL_DIR/.env"
        
        if [[ "$DATABASE_URL" =~ ^sqlite:/// ]]; then
            DB_PATH="${DATABASE_URL#sqlite:///}"
            if [[ -f "$BACKUP_DIR/$(basename $DB_PATH)" ]]; then
                cp "$BACKUP_DIR/$(basename $DB_PATH)" "$DB_PATH" 2>/dev/null || true
                print_success "SQLite database restored"
            fi
        fi
    fi
    
    # Restore configuration
    if [[ -f "$BACKUP_DIR/.env" ]]; then
        cp "$BACKUP_DIR/.env" "$INSTALL_DIR/" 2>/dev/null || true
        print_success "Configuration restored"
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
    echo "║          KAST-Web Update Script v1.0                  ║"
    echo "║                                                       ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}\n"
    
    if [[ "$DRY_RUN" == "yes" ]]; then
        print_warning "DRY RUN MODE - No changes will be made"
    fi
    
    # Initialize log file
    mkdir -p "$(dirname "$LOG_FILE")"
    touch "$LOG_FILE"
    log "KAST-Web Update Started"
    log "Update mode: $UPDATE_MODE"
    log "Command: $0 $*"
    
    # Pre-update checks
    check_root
    
    cd "$INSTALL_DIR" || error_exit "Failed to change to installation directory"
    
    validate_environment
    check_git_status
    get_version_info
    check_service_status
    
    # Show update summary
    print_header "Update Summary"
    echo -e "${CYAN}${BOLD}Update Configuration:${NC}"
    echo -e "  Update Mode: ${GREEN}$UPDATE_MODE${NC}"
    echo -e "  Current Version: ${GREEN}$CURRENT_VERSION${NC}"
    echo -e "  Target Version: ${GREEN}$INCOMING_VERSION${NC}"
    echo -e "  Create Backup: ${GREEN}$([ "$SKIP_BACKUP" == "yes" ] && echo "no" || echo "yes")${NC}"
    echo -e "  Auto Rollback: ${GREEN}$([ "$ROLLBACK_ON_FAILURE" == "yes" ] && echo "yes" || echo "no")${NC}"
    echo ""
    
    if [[ "$UPDATE_MODE" == "quick" ]]; then
        echo -e "${CYAN}Quick Update will:${NC}"
        echo "  • Pull latest code from git"
        echo "  • Restart services (~10-15 seconds downtime)"
    else
        echo -e "${CYAN}Full Update will:${NC}"
        echo "  • Pull latest code from git"
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
    perform_git_pull
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
    echo -e "  Previous Version: ${GREEN}$CURRENT_VERSION${NC}"
    
    NEW_VERSION=$(grep "^VERSION = " "$INSTALL_DIR/config.py" | cut -d"'" -f2)
    echo -e "  Current Version:  ${GREEN}$NEW_VERSION${NC}"
    
    if [[ "$SKIP_BACKUP" != "yes" ]]; then
        echo -e "  Backup Location:  ${GREEN}$BACKUP_DIR${NC}"
    fi
    
    echo -e "\n${CYAN}${BOLD}Service Status:${NC}"
    systemctl is-active --quiet kast-web && echo -e "  Web Application: ${GREEN}RUNNING${NC}" || echo -e "  Web Application: ${RED}STOPPED${NC}"
    systemctl is-active --quiet kast-celery && echo -e "  Celery Worker:   ${GREEN}RUNNING${NC}" || echo -e "  Celery Worker:   ${RED}STOPPED${NC}"
    
    echo -e "\n${CYAN}${BOLD}Next Steps:${NC}"
    echo "  • Test the application in your browser"
    echo "  • Check logs: sudo journalctl -u kast-web -f"
    echo "  • Monitor for any issues"
    
    if [[ "$SKIP_BACKUP" != "yes" ]]; then
        echo "  • Rollback if needed: sudo ./scripts/rollback.sh"
    fi
    
    echo -e "\n${GREEN}Update log saved to: $LOG_FILE${NC}\n"
    
    log "KAST-Web Update Completed Successfully"
}

# Run main function
main "$@"
