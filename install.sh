#!/bin/bash

################################################################################
# KAST-Web Installer Script
# Version: 1.0.0
# Description: Comprehensive installer for KAST-Web security scanning interface
# Usage: sudo ./install.sh [options]
################################################################################

set -e  # Exit on error
set -o pipefail  # Catch errors in pipes

################################################################################
# Configuration Variables
################################################################################

INSTALL_DIR="/opt/kast-web"
KAST_CLI_PATH="/usr/local/bin/kast"
LOG_FILE="/var/log/kast-web-install.log"
BACKUP_BASE_DIR="/opt/kast-web-backup"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_USER="www-data"

# Default values (can be overridden by command-line arguments)
DATABASE_TYPE="sqlite"
WEB_SERVER=""
INSTALL_SSL="no"
SSL_EXPLICITLY_SET="no"
DOMAIN_NAME=""
NON_INTERACTIVE="no"
ADMIN_USERNAME=""
ADMIN_EMAIL=""
ADMIN_PASSWORD=""
ADMIN_FIRST_NAME=""
ADMIN_LAST_NAME=""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Arrays to store warnings
declare -a WARNINGS=()
declare -a FIREWALL_WARNINGS=()

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

# Progress indicator
show_progress() {
    echo -ne "${BLUE}$1...${NC}\r"
}

# Error handler
error_exit() {
    print_error "$1"
    log "Installation failed. Check $LOG_FILE for details."
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

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --database=*)
                DATABASE_TYPE="${1#*=}"
                shift
                ;;
            --web-server=*)
                WEB_SERVER="${1#*=}"
                shift
                ;;
            --ssl)
                INSTALL_SSL="yes"
                SSL_EXPLICITLY_SET="yes"
                shift
                ;;
            --no-ssl)
                INSTALL_SSL="no"
                SSL_EXPLICITLY_SET="yes"
                shift
                ;;
            --domain=*)
                DOMAIN_NAME="${1#*=}"
                shift
                ;;
            --admin-user=*)
                ADMIN_USERNAME="${1#*=}"
                shift
                ;;
            --admin-email=*)
                ADMIN_EMAIL="${1#*=}"
                shift
                ;;
            --admin-pass=*)
                ADMIN_PASSWORD="${1#*=}"
                shift
                ;;
            --admin-first-name=*)
                ADMIN_FIRST_NAME="${1#*=}"
                shift
                ;;
            --admin-last-name=*)
                ADMIN_LAST_NAME="${1#*=}"
                shift
                ;;
            --non-interactive)
                NON_INTERACTIVE="yes"
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

show_help() {
    cat << EOF
KAST-Web Installer

Usage: sudo ./install.sh [options]

Options:
  --database=TYPE          Database type: sqlite, postgresql, mysql, mariadb (default: sqlite)
  --web-server=SERVER      Web server: nginx, apache (default: auto-detect or nginx)
  --ssl                    Install and configure SSL with Let's Encrypt
  --no-ssl                 Skip SSL installation (default)
  --domain=DOMAIN          Domain name for web server configuration
  --admin-user=USERNAME    Admin username for initial user
  --admin-email=EMAIL      Admin email address
  --admin-pass=PASSWORD    Admin password
  --admin-first-name=NAME  Admin first name (optional)
  --admin-last-name=NAME   Admin last name (optional)
  --non-interactive        Run in non-interactive mode (requires all parameters)
  --help, -h               Show this help message

Examples:
  # Interactive installation
  sudo ./install.sh

  # Non-interactive with PostgreSQL and SSL
  sudo ./install.sh --database=postgresql --ssl --domain=kast.example.com \\
    --admin-user=admin --admin-email=admin@example.com --admin-pass=SecurePass123

  # Nginx with SQLite (default), no SSL
  sudo ./install.sh --web-server=nginx --no-ssl --domain=kast.local \\
    --admin-user=admin --admin-email=admin@example.com --admin-pass=SecurePass123

EOF
}

################################################################################
# User Input Collection (Interactive Mode Only)
################################################################################

collect_user_inputs() {
    if [[ "$NON_INTERACTIVE" == "yes" ]]; then
        return 0
    fi
    
    print_header "Installation Configuration"
    
    echo -e "${CYAN}This installer will now collect all necessary information upfront.${NC}"
    echo -e "${CYAN}After providing your inputs, the installation will run unattended.${NC}\n"
    
    # 1. Check for existing installation first
    if [[ -d "$INSTALL_DIR" ]]; then
        print_warning "Existing installation detected at $INSTALL_DIR"
        echo ""
        echo "Choose an action:"
        echo "  [1] Backup and upgrade existing installation"
        echo "  [2] Fresh install (remove existing installation)"
        echo "  [3] Abort installation"
        echo ""
        read -p "Enter choice [1-3]: " -r EXISTING_INSTALL_CHOICE
        
        case $EXISTING_INSTALL_CHOICE in
            1|2|3)
                # Valid choice
                ;;
            *)
                error_exit "Invalid choice"
                ;;
        esac
        
        if [[ "$EXISTING_INSTALL_CHOICE" == "3" ]]; then
            print_info "Installation aborted by user"
            exit 0
        fi
        echo ""
    fi
    
    # 2. Detect web servers for intelligent prompting
    APACHE_DETECTED="no"
    NGINX_DETECTED="no"
    
    if command -v apache2 &>/dev/null || command -v httpd &>/dev/null; then
        APACHE_DETECTED="yes"
    fi
    
    if command -v nginx &>/dev/null; then
        NGINX_DETECTED="yes"
    fi
    
    # 3. Database type selection
    if [[ -z "$DATABASE_TYPE" ]]; then
        echo -e "${BOLD}Database Configuration:${NC}"
        echo "Select database type:"
        echo "  [1] SQLite (default - no additional setup required)"
        echo "  [2] PostgreSQL (recommended for production)"
        echo "  [3] MySQL"
        echo "  [4] MariaDB"
        echo ""
        read -p "Enter choice [1-4] (default: 1): " -r db_choice
        db_choice=${db_choice:-1}
        
        case $db_choice in
            1) DATABASE_TYPE="sqlite" ;;
            2) DATABASE_TYPE="postgresql" ;;
            3) DATABASE_TYPE="mysql" ;;
            4) DATABASE_TYPE="mariadb" ;;
            *) DATABASE_TYPE="sqlite" ;;
        esac
        echo ""
    fi
    
    # 4. Web server selection
    if [[ -z "$WEB_SERVER" ]]; then
        echo -e "${BOLD}Web Server Configuration:${NC}"
        
        if [[ "$APACHE_DETECTED" == "yes" && "$NGINX_DETECTED" == "yes" ]]; then
            echo "Both Apache and Nginx are installed. Which would you like to use?"
            echo "  [1] Nginx (recommended)"
            echo "  [2] Apache"
            read -p "Enter choice [1-2]: " -r ws_choice
            
            case $ws_choice in
                1) WEB_SERVER="nginx" ;;
                2) WEB_SERVER="apache" ;;
                *) WEB_SERVER="nginx" ;;
            esac
        elif [[ "$APACHE_DETECTED" == "yes" ]]; then
            WEB_SERVER="apache"
            print_info "Apache detected - will use Apache"
        elif [[ "$NGINX_DETECTED" == "yes" ]]; then
            WEB_SERVER="nginx"
            print_info "Nginx detected - will use Nginx"
        else
            WEB_SERVER="nginx"
            print_info "No web server detected - will install Nginx"
        fi
        echo ""
    fi
    
    # 5. Domain name
    if [[ -z "$DOMAIN_NAME" ]]; then
        echo -e "${BOLD}Domain Configuration:${NC}"
        read -p "Enter domain name (or press Enter for 'localhost'): " DOMAIN_NAME
        DOMAIN_NAME=${DOMAIN_NAME:-localhost}
        echo ""
    fi
    
    # 6. SSL configuration
    if [[ "$SSL_EXPLICITLY_SET" == "no" ]]; then
        echo -e "${BOLD}SSL Configuration:${NC}"
        
        if [[ "$DOMAIN_NAME" == "localhost" || "$DOMAIN_NAME" == "127.0.0.1" ]]; then
            print_info "SSL not available for localhost - will skip SSL configuration"
            INSTALL_SSL="no"
        else
            read -p "Install Let's Encrypt SSL certificate? (y/N): " -r ssl_choice
            if [[ "$ssl_choice" =~ ^[Yy]$ ]]; then
                INSTALL_SSL="yes"
            else
                INSTALL_SSL="no"
            fi
        fi
        echo ""
    fi
    
    # 7. Admin user credentials
    echo -e "${BOLD}Admin User Configuration:${NC}"
    
    if [[ -z "$ADMIN_USERNAME" ]]; then
        read -p "Admin username (3-80 characters): " ADMIN_USERNAME
        while [[ ${#ADMIN_USERNAME} -lt 3 ]]; do
            print_error "Username must be at least 3 characters"
            read -p "Admin username (3-80 characters): " ADMIN_USERNAME
        done
    fi
    
    if [[ -z "$ADMIN_EMAIL" ]]; then
        read -p "Admin email: " ADMIN_EMAIL
        while [[ ! "$ADMIN_EMAIL" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; do
            print_error "Please enter a valid email address"
            read -p "Admin email: " ADMIN_EMAIL
        done
    fi
    
    if [[ -z "$ADMIN_FIRST_NAME" ]]; then
        read -p "Admin first name (optional, press Enter to skip): " ADMIN_FIRST_NAME
    fi
    
    if [[ -z "$ADMIN_LAST_NAME" ]]; then
        read -p "Admin last name (optional, press Enter to skip): " ADMIN_LAST_NAME
    fi
    
    if [[ -z "$ADMIN_PASSWORD" ]]; then
        while true; do
            read -s -p "Admin password (min 8 characters): " ADMIN_PASSWORD
            echo ""
            
            if [[ ${#ADMIN_PASSWORD} -lt 8 ]]; then
                print_error "Password must be at least 8 characters"
                continue
            fi
            
            read -s -p "Confirm password: " ADMIN_PASSWORD_CONFIRM
            echo ""
            
            if [[ "$ADMIN_PASSWORD" != "$ADMIN_PASSWORD_CONFIRM" ]]; then
                print_error "Passwords do not match"
                ADMIN_PASSWORD=""
                continue
            fi
            
            break
        done
    fi
    
    echo ""
    
    # 8. Display summary and confirm
    print_header "Installation Summary"
    
    echo -e "${CYAN}${BOLD}Please review your configuration:${NC}\n"
    
    if [[ -n "$EXISTING_INSTALL_CHOICE" ]]; then
        case $EXISTING_INSTALL_CHOICE in
            1) echo -e "  Existing Installation: ${GREEN}Backup and upgrade${NC}" ;;
            2) echo -e "  Existing Installation: ${YELLOW}Fresh install (will remove existing)${NC}" ;;
        esac
    fi
    
    echo -e "  Database Type:         ${GREEN}$DATABASE_TYPE${NC}"
    echo -e "  Web Server:            ${GREEN}$WEB_SERVER${NC}"
    echo -e "  Domain Name:           ${GREEN}$DOMAIN_NAME${NC}"
    echo -e "  SSL Certificate:       ${GREEN}$INSTALL_SSL${NC}"
    echo -e "  Admin Username:        ${GREEN}$ADMIN_USERNAME${NC}"
    echo -e "  Admin Email:           ${GREEN}$ADMIN_EMAIL${NC}"
    
    if [[ -n "$ADMIN_FIRST_NAME" ]]; then
        echo -e "  Admin First Name:      ${GREEN}$ADMIN_FIRST_NAME${NC}"
    fi
    
    if [[ -n "$ADMIN_LAST_NAME" ]]; then
        echo -e "  Admin Last Name:       ${GREEN}$ADMIN_LAST_NAME${NC}"
    fi
    
    echo ""
    read -p "Proceed with installation? (Y/n): " -r proceed_choice
    
    if [[ "$proceed_choice" =~ ^[Nn]$ ]]; then
        print_info "Installation cancelled by user"
        exit 0
    fi
    
    print_success "Configuration confirmed - starting installation..."
    echo ""
}

################################################################################
# Pre-Installation Checks
################################################################################

check_os() {
    print_header "System Compatibility Check"
    
    if [[ ! -f /etc/os-release ]]; then
        error_exit "Cannot determine OS. /etc/os-release not found."
    fi
    
    source /etc/os-release
    
    case $ID in
        ubuntu|debian|kali)
            print_success "OS: $PRETTY_NAME (Supported)"
            ;;
        *)
            print_warning "OS: $PRETTY_NAME (Not officially tested)"
            WARNINGS+=("Your OS ($PRETTY_NAME) is not officially tested. Installation may fail.")
            ;;
    esac
    
    log "OS: $PRETTY_NAME"
    log "Kernel: $(uname -r)"
}

check_kast_cli() {
    print_header "KAST CLI Validation"
    
    if [[ ! -f "$KAST_CLI_PATH" ]]; then
        error_exit "KAST CLI not found at $KAST_CLI_PATH. Please install KAST first."
    fi
    
    if [[ ! -x "$KAST_CLI_PATH" ]]; then
        error_exit "KAST CLI at $KAST_CLI_PATH is not executable. Run: chmod +x $KAST_CLI_PATH"
    fi
    
    print_success "KAST CLI found at $KAST_CLI_PATH"
    
    # Test KAST CLI
    show_progress "Testing KAST CLI"
    if $KAST_CLI_PATH -ls &>/dev/null; then
        PLUGIN_COUNT=$($KAST_CLI_PATH -ls 2>/dev/null | grep -c "(priority:")
        print_success "KAST CLI is functional ($PLUGIN_COUNT plugins detected)"
    else
        error_exit "KAST CLI test failed. Cannot execute: $KAST_CLI_PATH --list-plugins"
    fi
}

configure_kast_permissions() {
    print_header "KAST Log Directory Permissions"
    
    # Check if /var/log/kast exists
    if [[ ! -d /var/log/kast ]]; then
        print_info "/var/log/kast does not exist yet - will be created by KAST CLI on first use"
        print_info "Note: Run this script again after first KAST CLI usage to fix permissions"
        return 0
    fi
    
    print_info "Configuring /var/log/kast for shared access..."
    
    # Create kast group if it doesn't exist
    if ! getent group kast > /dev/null 2>&1; then
        groupadd kast >> "$LOG_FILE" 2>&1
        print_success "Created 'kast' group for shared KAST operations"
    else
        print_success "'kast' group already exists"
    fi
    
    # Add www-data to kast group
    if id -nG www-data | grep -qw kast; then
        print_success "www-data user already in 'kast' group"
    else
        usermod -aG kast www-data >> "$LOG_FILE" 2>&1
        print_success "Added www-data user to 'kast' group"
    fi
    
    # Get current owner of /var/log/kast
    KAST_LOG_OWNER=$(stat -c '%U' /var/log/kast 2>/dev/null)
    
    if [[ -n "$KAST_LOG_OWNER" ]]; then
        # Add the current owner to kast group as well
        if id -nG "$KAST_LOG_OWNER" | grep -qw kast; then
            print_success "Directory owner '$KAST_LOG_OWNER' already in 'kast' group"
        else
            usermod -aG kast "$KAST_LOG_OWNER" >> "$LOG_FILE" 2>&1 || true
            print_success "Added directory owner '$KAST_LOG_OWNER' to 'kast' group"
        fi
        
        # Set ownership to preserve original owner but use kast group
        chown "$KAST_LOG_OWNER:kast" /var/log/kast >> "$LOG_FILE" 2>&1
        print_success "Set ownership to $KAST_LOG_OWNER:kast"
    else
        # Fallback if we can't determine owner
        chown root:kast /var/log/kast >> "$LOG_FILE" 2>&1
        print_success "Set ownership to root:kast"
    fi
    
    # Set permissions: 775 with setgid bit (2775)
    # This ensures new files inherit the group
    chmod 2775 /var/log/kast >> "$LOG_FILE" 2>&1
    print_success "Set permissions to 2775 (rwxrwsr-x) with setgid bit"
    
    # Also fix existing log files
    if [[ -n "$(ls -A /var/log/kast 2>/dev/null)" ]]; then
        chown -R "$KAST_LOG_OWNER:kast" /var/log/kast/* >> "$LOG_FILE" 2>&1 || true
        chmod -R 664 /var/log/kast/* >> "$LOG_FILE" 2>&1 || true
        print_success "Updated permissions for existing log files"
    fi
    
    print_success "KAST log directory configured for shared access"
    log "KAST permissions: Owner=$KAST_LOG_OWNER, Group=kast, Mode=2775"
}

configure_security_tool_configs() {
    print_header "Security Tool Configuration for www-data"
    
    print_info "Setting up configuration directories for security tools..."
    
    # Create config directory structure for www-data
    mkdir -p /var/www/.config/katana >> "$LOG_FILE" 2>&1
    mkdir -p /var/www/.config/subfinder >> "$LOG_FILE" 2>&1
    
    print_success "Created config directories in /var/www/.config/"
    
    # Check if user has existing configs and copy them
    # Get the actual user who invoked sudo (not root)
    ACTUAL_USER="${SUDO_USER:-$USER}"
    ACTUAL_HOME=$(getent passwd "$ACTUAL_USER" | cut -d: -f6)
    
    # Copy katana config if it exists
    if [[ -f "$ACTUAL_HOME/.config/katana/config.yaml" ]]; then
        cp "$ACTUAL_HOME/.config/katana/config.yaml" /var/www/.config/katana/ >> "$LOG_FILE" 2>&1
        print_success "Copied katana config from $ACTUAL_USER's home directory"
    else
        # Create minimal config file
        touch /var/www/.config/katana/config.yaml
        print_info "Created empty katana config (tool will use defaults)"
    fi
    
    # Copy subfinder config if it exists
    if [[ -f "$ACTUAL_HOME/.config/subfinder/config.yaml" ]]; then
        cp "$ACTUAL_HOME/.config/subfinder/config.yaml" /var/www/.config/subfinder/ >> "$LOG_FILE" 2>&1
        print_success "Copied subfinder config from $ACTUAL_USER's home directory"
    else
        # Create minimal config file
        touch /var/www/.config/subfinder/config.yaml
        print_info "Created empty subfinder config (tool will use defaults)"
    fi
    
    # Set proper ownership
    chown -R www-data:www-data /var/www/.config >> "$LOG_FILE" 2>&1
    print_success "Set ownership to www-data:www-data"
    
    # Set proper permissions
    chmod -R 755 /var/www/.config >> "$LOG_FILE" 2>&1
    find /var/www/.config -type f -exec chmod 644 {} \; >> "$LOG_FILE" 2>&1
    print_success "Set permissions (directories: 755, files: 644)"
    
    # Test katana if available
    if command -v katana &>/dev/null; then
        print_info "Testing katana configuration..."
        if sudo -u www-data katana -version &>/dev/null; then
            print_success "Katana can be executed by www-data"
        else
            print_warning "Katana test failed - may need manual configuration"
            WARNINGS+=("Katana may require additional configuration for www-data user")
        fi
    fi
    
    print_success "Security tool configurations set up for www-data"
    log "Config directories: /var/www/.config/katana, /var/www/.config/subfinder"
}

check_disk_space() {
    print_header "Disk Space Check"
    
    AVAILABLE_SPACE=$(df /opt | tail -1 | awk '{print $4}')
    REQUIRED_SPACE=1048576  # 1GB in KB
    
    if [[ $AVAILABLE_SPACE -lt $REQUIRED_SPACE ]]; then
        error_exit "Insufficient disk space. Required: 1GB, Available: $((AVAILABLE_SPACE/1024))MB"
    fi
    
    print_success "Sufficient disk space available: $((AVAILABLE_SPACE/1024/1024))GB"
}

check_existing_installation() {
    print_header "Existing Installation Check"
    
    if [[ -d "$INSTALL_DIR" ]]; then
        print_warning "Existing installation detected at $INSTALL_DIR"
        
        if [[ "$NON_INTERACTIVE" == "yes" ]]; then
            error_exit "Non-interactive mode cannot handle existing installations. Please remove manually."
        fi
        
        # Use pre-collected choice from collect_user_inputs()
        if [[ -n "$EXISTING_INSTALL_CHOICE" ]]; then
            case $EXISTING_INSTALL_CHOICE in
                1)
                    backup_existing_installation
                    UPGRADE_MODE="yes"
                    ;;
                2)
                    print_warning "Removing existing installation..."
                    systemctl stop kast-web kast-celery 2>/dev/null || true
                    rm -rf "$INSTALL_DIR"
                    print_success "Existing installation removed"
                    UPGRADE_MODE="no"
                    ;;
            esac
        else
            error_exit "Installation choice not collected"
        fi
    else
        print_success "No existing installation found"
        UPGRADE_MODE="no"
    fi
}

backup_existing_installation() {
    BACKUP_DIR="${BACKUP_BASE_DIR}-$(date +%Y%m%d-%H%M%S)"
    
    print_info "Creating backup at $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
    
    # Backup database
    if [[ -f "$INSTALL_DIR/.env" ]]; then
        source "$INSTALL_DIR/.env"
        
        if [[ "$DATABASE_URL" =~ ^sqlite:/// ]]; then
            DB_PATH="${DATABASE_URL#sqlite:///}"
            if [[ -f "$DB_PATH" ]]; then
                cp "$DB_PATH" "$BACKUP_DIR/"
                print_success "Database backed up"
            fi
        elif [[ "$DATABASE_URL" =~ ^postgresql:// ]]; then
            # Extract database name from URL
            DB_NAME=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
            sudo -u postgres pg_dump "$DB_NAME" > "$BACKUP_DIR/database.sql"
            print_success "PostgreSQL database dumped"
        elif [[ "$DATABASE_URL" =~ ^mysql:// ]]; then
            DB_NAME=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
            DB_USER=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
            DB_PASS=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
            mysqldump -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" > "$BACKUP_DIR/database.sql"
            print_success "MySQL database dumped"
        fi
    fi
    
    # Backup configuration
    [[ -f "$INSTALL_DIR/.env" ]] && cp "$INSTALL_DIR/.env" "$BACKUP_DIR/"
    
    # Backup uploads
    if [[ -d "$INSTALL_DIR/app/static/uploads" ]]; then
        cp -r "$INSTALL_DIR/app/static/uploads" "$BACKUP_DIR/"
        print_success "Upload files backed up"
    fi
    
    # Create backup info file
    cat > "$BACKUP_DIR/backup-info.txt" << EOF
Backup created: $(date)
Installation directory: $INSTALL_DIR
Backup directory: $BACKUP_DIR
EOF
    
    print_success "Backup completed at $BACKUP_DIR"
    log "Backup location: $BACKUP_DIR"
}

################################################################################
# System Dependencies Installation
################################################################################

install_system_dependencies() {
    print_header "Installing System Dependencies"
    
    show_progress "Updating package lists"
    apt-get update >> "$LOG_FILE" 2>&1
    print_success "Package lists updated"
    
    show_progress "Installing base dependencies"
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        build-essential \
        redis-server \
        sqlite3 \
        curl \
        wget \
        git \
        >> "$LOG_FILE" 2>&1
    print_success "Base dependencies installed"
    
    # Start and enable Redis
    systemctl enable redis-server >> "$LOG_FILE" 2>&1
    systemctl start redis-server >> "$LOG_FILE" 2>&1
    print_success "Redis server enabled and started"
    
    # Test Redis
    if redis-cli ping &>/dev/null; then
        print_success "Redis is responding"
    else
        error_exit "Redis installation failed - not responding to ping"
    fi
}

################################################################################
# Database Configuration
################################################################################

configure_database() {
    print_header "Database Configuration"
    
    # Database type should already be set by collect_user_inputs() or command-line args
    if [[ -z "$DATABASE_TYPE" ]]; then
        DATABASE_TYPE="sqlite"
    fi
    
    print_info "Selected database: $DATABASE_TYPE"
    
    case $DATABASE_TYPE in
        sqlite)
            configure_sqlite
            ;;
        postgresql)
            configure_postgresql
            ;;
        mysql)
            configure_mysql
            ;;
        mariadb)
            configure_mariadb
            ;;
        *)
            error_exit "Unknown database type: $DATABASE_TYPE"
            ;;
    esac
}

configure_sqlite() {
    print_success "SQLite selected - no additional setup required"
    DB_DIR="/var/lib/kast-web"
    mkdir -p "$DB_DIR"
    # Ensure proper ownership for the database directory
    chown -R $SERVICE_USER:$SERVICE_USER "$DB_DIR"
    DATABASE_URL="sqlite:///$DB_DIR/kast.db"
    print_info "Database will be stored at: $DB_DIR/kast.db"
}

configure_postgresql() {
    print_info "Installing PostgreSQL..."
    apt-get install -y postgresql postgresql-contrib python3-psycopg2 >> "$LOG_FILE" 2>&1
    print_success "PostgreSQL installed"
    
    systemctl enable postgresql >> "$LOG_FILE" 2>&1
    systemctl start postgresql >> "$LOG_FILE" 2>&1
    
    # Generate database credentials
    DB_NAME="kast_web"
    DB_USER="kast_user"
    DB_PASS=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 24)
    
    print_info "Creating PostgreSQL database and user..."
    
    sudo -u postgres psql << EOF >> "$LOG_FILE" 2>&1
CREATE DATABASE $DB_NAME;
CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
\c $DB_NAME
GRANT ALL ON SCHEMA public TO $DB_USER;
EOF
    
    print_success "PostgreSQL database configured"
    DATABASE_URL="postgresql://$DB_USER:$DB_PASS@localhost/$DB_NAME"
    
    log "PostgreSQL credentials: User=$DB_USER, DB=$DB_NAME"
}

configure_mysql() {
    print_info "Installing MySQL..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y mysql-server python3-mysqldb >> "$LOG_FILE" 2>&1
    print_success "MySQL installed"
    
    systemctl enable mysql >> "$LOG_FILE" 2>&1
    systemctl start mysql >> "$LOG_FILE" 2>&1
    
    # Generate database credentials
    DB_NAME="kast_web"
    DB_USER="kast_user"
    DB_PASS=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 24)
    
    print_info "Creating MySQL database and user..."
    
    mysql << EOF >> "$LOG_FILE" 2>&1
CREATE DATABASE $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';
GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost';
FLUSH PRIVILEGES;
EOF
    
    print_success "MySQL database configured"
    DATABASE_URL="mysql+pymysql://$DB_USER:$DB_PASS@localhost/$DB_NAME"
    
    log "MySQL credentials: User=$DB_USER, DB=$DB_NAME"
}

configure_mariadb() {
    print_info "Installing MariaDB..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y mariadb-server python3-mysqldb >> "$LOG_FILE" 2>&1
    print_success "MariaDB installed"
    
    systemctl enable mariadb >> "$LOG_FILE" 2>&1
    systemctl start mariadb >> "$LOG_FILE" 2>&1
    
    # Generate database credentials
    DB_NAME="kast_web"
    DB_USER="kast_user"
    DB_PASS=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 24)
    
    print_info "Creating MariaDB database and user..."
    
    mysql << EOF >> "$LOG_FILE" 2>&1
CREATE DATABASE $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';
GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost';
FLUSH PRIVILEGES;
EOF
    
    print_success "MariaDB database configured"
    DATABASE_URL="mysql+pymysql://$DB_USER:$DB_PASS@localhost/$DB_NAME"
    
    log "MariaDB credentials: User=$DB_USER, DB=$DB_NAME"
}

################################################################################
# Application Setup
################################################################################

setup_application() {
    print_header "Application Setup"
    
    # Create directories
    mkdir -p "$INSTALL_DIR"
    mkdir -p /var/log/kast-web
    mkdir -p /var/run/kast-web
    mkdir -p /var/lib/kast-web/results
    
    # Set ownership
    chown -R $SERVICE_USER:$SERVICE_USER /var/log/kast-web
    chown -R $SERVICE_USER:$SERVICE_USER /var/run/kast-web
    chown -R $SERVICE_USER:$SERVICE_USER /var/lib/kast-web
    
    print_success "Directories created"
    
    # Determine source directory (where install.sh is located)
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # Copy application files to installation directory
    print_info "Copying application files from $SCRIPT_DIR to $INSTALL_DIR..."
    rsync -av --exclude='venv' --exclude='*.pyc' --exclude='__pycache__' \
        --exclude='.git' --exclude='*.log' --exclude='instance' \
        --exclude='*.db' --exclude='*.sqlite' --exclude='*.sqlite3' \
        "$SCRIPT_DIR/" "$INSTALL_DIR/" >> "$LOG_FILE" 2>&1
    
    print_success "Application files copied"
    
    # Create virtual environment
    if [[ ! -d "$VENV_DIR" ]]; then
        print_info "Creating Python virtual environment..."
        python3 -m venv "$VENV_DIR" >> "$LOG_FILE" 2>&1
        print_success "Virtual environment created"
    else
        print_success "Virtual environment already exists"
    fi
    
    # Install Python dependencies
    print_info "Installing Python dependencies (this may take a few minutes)..."
    source "$VENV_DIR/bin/activate"
    
    if ! pip install --upgrade pip >> "$LOG_FILE" 2>&1; then
        error_exit "Failed to upgrade pip. Check $LOG_FILE for details."
    fi
    
    if [[ -f "$INSTALL_DIR/requirements-production.txt" ]]; then
        if ! pip install -r "$INSTALL_DIR/requirements-production.txt" >> "$LOG_FILE" 2>&1; then
            print_error "Failed to install Python dependencies"
            echo ""
            echo "Last 50 lines of error log:"
            tail -50 "$LOG_FILE"
            echo ""
            error_exit "Python dependency installation failed. See above for details."
        fi
    elif [[ -f "$INSTALL_DIR/requirements.txt" ]]; then
        if ! pip install -r "$INSTALL_DIR/requirements.txt" >> "$LOG_FILE" 2>&1; then
            print_error "Failed to install Python dependencies"
            echo ""
            echo "Last 50 lines of error log:"
            tail -50 "$LOG_FILE"
            echo ""
            error_exit "Python dependency installation failed. See above for details."
        fi
        if ! pip install gunicorn >> "$LOG_FILE" 2>&1; then
            error_exit "Failed to install gunicorn. Check $LOG_FILE for details."
        fi
    else
        error_exit "No requirements file found"
    fi
    
    # Install database-specific drivers
    case $DATABASE_TYPE in
        postgresql)
            pip install psycopg2-binary >> "$LOG_FILE" 2>&1
            ;;
        mysql|mariadb)
            pip install PyMySQL >> "$LOG_FILE" 2>&1
            ;;
    esac
    
    print_success "Python dependencies installed"
    
    # Generate secret key
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    
    # Create .env file
    print_info "Creating configuration file..."
    cat > "$INSTALL_DIR/.env" << EOF
# KAST-Web Configuration
# Generated: $(date)

FLASK_ENV=production
SECRET_KEY=$SECRET_KEY

# Database Configuration
DATABASE_URL=$DATABASE_URL

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# KAST CLI Configuration
KAST_CLI_PATH=$KAST_CLI_PATH
KAST_RESULTS_DIR=/var/lib/kast-web/results
EOF
    
    chmod 600 "$INSTALL_DIR/.env"
    chown $SERVICE_USER:$SERVICE_USER "$INSTALL_DIR/.env"
    print_success "Configuration file created"
    
    # Verify and fix ownership of all application files
    print_info "Verifying file ownership..."
    chown -R $SERVICE_USER:$SERVICE_USER "$INSTALL_DIR"
    # Preserve execute permissions on scripts
    chmod +x "$INSTALL_DIR/scripts"/*.sh 2>/dev/null || true
    print_success "File ownership verified"
}

initialize_database() {
    print_header "Database Initialization"
    
    cd "$INSTALL_DIR" || error_exit "Failed to change to installation directory"
    source "$VENV_DIR/bin/activate" || error_exit "Failed to activate virtual environment"
    
    # Load and export all .env variables to ensure Flask reads them
    set -a
    source "$INSTALL_DIR/.env"
    set +a
    
    # Set PYTHONPATH so migrations can import app module
    export PYTHONPATH="$INSTALL_DIR"
    
    # Run database migrations if they exist
    if [[ -d "$INSTALL_DIR/utils" ]]; then
        print_info "Running database migrations..."
        
        # Set environment variable for non-interactive mode
        export NON_INTERACTIVE=1
        
        for migration in "$INSTALL_DIR"/utils/migrate*.py; do
            if [[ -f "$migration" ]]; then
                print_info "Running migration: $(basename "$migration")"
                # Pass --non-interactive flag to all migration scripts
                python3 "$migration" --non-interactive >> "$LOG_FILE" 2>&1 || true
            fi
        done
        
        # Unset the environment variable
        unset NON_INTERACTIVE
    fi
    
    # Initialize database tables
    print_info "Initializing database tables..."
    if python3 << 'EOF' >> "$LOG_FILE" 2>&1
import os
import sys

# Set working directory explicitly to prevent creating files in /root
os.chdir('/opt/kast-web')

from app import create_app, db
app = create_app()
with app.app_context():
    db.create_all()
    print("Database tables created successfully")
EOF
    then
        print_success "Database initialized"
        
        # Fix database file ownership for SQLite
        if [[ "$DATABASE_TYPE" == "sqlite" ]]; then
            DB_FILE="/var/lib/kast-web/kast.db"
            if [[ -f "$DB_FILE" ]]; then
                chown $SERVICE_USER:$SERVICE_USER "$DB_FILE"
                chmod 664 "$DB_FILE"
                print_success "Database file ownership set to $SERVICE_USER:$SERVICE_USER"
            fi
        fi
    else
        error_exit "Database initialization failed. Check $LOG_FILE for details."
    fi
}

create_admin_user() {
    print_header "Admin User Creation"
    
    cd "$INSTALL_DIR" || error_exit "Failed to change to installation directory"
    source "$VENV_DIR/bin/activate" || error_exit "Failed to activate virtual environment"
    
    # Admin credentials should already be set by collect_user_inputs() or command-line args
    # Validate inputs
    if [[ -z "$ADMIN_USERNAME" ]] || [[ -z "$ADMIN_EMAIL" ]] || [[ -z "$ADMIN_PASSWORD" ]]; then
        error_exit "Admin username, email, and password are required"
    fi
    
    if [[ ${#ADMIN_USERNAME} -lt 3 ]]; then
        error_exit "Admin username must be at least 3 characters"
    fi
    
    if [[ ${#ADMIN_PASSWORD} -lt 8 ]]; then
        error_exit "Admin password must be at least 8 characters"
    fi
    
    # Create admin user
    print_info "Creating admin user..."
    
    # Load and export all .env variables to ensure Flask reads them
    set -a
    source "$INSTALL_DIR/.env"
    set +a
    
    # Export admin credentials as environment variables
    export ADMIN_USERNAME
    export ADMIN_EMAIL
    export ADMIN_PASSWORD
    export ADMIN_FIRST_NAME
    export ADMIN_LAST_NAME
    export PYTHONPATH="$INSTALL_DIR"
    
    # Use single-quoted heredoc to prevent shell variable expansion
    python3 << 'EOF' >> "$LOG_FILE" 2>&1
import os
import sys

# Set working directory explicitly to prevent creating files in /root
os.chdir('/opt/kast-web')

from app import create_app, db
from app.models import User

# Get credentials from environment variables
username = os.environ.get('ADMIN_USERNAME')
email = os.environ.get('ADMIN_EMAIL')
password = os.environ.get('ADMIN_PASSWORD')
first_name = os.environ.get('ADMIN_FIRST_NAME', '')
last_name = os.environ.get('ADMIN_LAST_NAME', '')

app = create_app()
with app.app_context():
    # Check if user already exists
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        print("User already exists, skipping creation")
        sys.exit(0)
    
    admin_user = User(
        username=username,
        email=email,
        first_name=first_name if first_name else None,
        last_name=last_name if last_name else None,
        role='admin',
        is_active=True
    )
    admin_user.set_password(password)
    db.session.add(admin_user)
    db.session.commit()
    print("Admin user created successfully")
EOF
    
    if [ $? -eq 0 ]; then
        print_success "Admin user created: $ADMIN_USERNAME"
    else
        error_exit "Failed to create admin user"
    fi
}

################################################################################
# Web Server Configuration
################################################################################

detect_web_server() {
    print_header "Web Server Detection"
    
    # Web server should already be set by collect_user_inputs() or command-line args
    if [[ -z "$WEB_SERVER" ]]; then
        # Fallback for non-interactive mode
        WEB_SERVER="nginx"
    fi
    
    print_success "Selected web server: $WEB_SERVER"
}

configure_nginx() {
    print_header "Nginx Configuration"
    
    # Install Nginx if not present
    if ! command -v nginx &>/dev/null; then
        print_info "Installing Nginx..."
        apt-get install -y nginx >> "$LOG_FILE" 2>&1
        print_success "Nginx installed"
    fi
    
    # Domain name should already be set by collect_user_inputs() or command-line args
    DOMAIN_NAME=${DOMAIN_NAME:-localhost}
    
    # Create Nginx configuration
    print_info "Creating Nginx configuration..."
    cat > /etc/nginx/sites-available/kast-web << 'NGINXEOF'
upstream kast_web {
    server 127.0.0.1:8000 fail_timeout=0;
}

server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER;
    
    client_max_body_size 16M;
    
    access_log /var/log/nginx/kast-web-access.log;
    error_log /var/log/nginx/kast-web-error.log;
    
    location /static {
        alias /opt/kast-web/app/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    location / {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        
        proxy_buffering off;
        proxy_redirect off;
        proxy_pass http://kast_web;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
NGINXEOF
    
    # Replace domain placeholder
    sed -i "s/DOMAIN_PLACEHOLDER/$DOMAIN_NAME/" /etc/nginx/sites-available/kast-web
    
    # Enable site
    ln -sf /etc/nginx/sites-available/kast-web /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # Test configuration
    if nginx -t >> "$LOG_FILE" 2>&1; then
        print_success "Nginx configuration valid"
    else
        error_exit "Nginx configuration test failed"
    fi
    
    # Restart Nginx
    systemctl enable nginx >> "$LOG_FILE" 2>&1
    systemctl restart nginx >> "$LOG_FILE" 2>&1
    print_success "Nginx configured and restarted"
}

configure_apache() {
    print_header "Apache Configuration"
    
    # Install Apache if not present
    if ! command -v apache2 &>/dev/null && ! command -v httpd &>/dev/null; then
        print_info "Installing Apache..."
        apt-get install -y apache2 >> "$LOG_FILE" 2>&1
        print_success "Apache installed"
    fi
    
    # Determine Apache command (apache2 on Debian/Ubuntu, httpd on others)
    if command -v apache2 &>/dev/null; then
        APACHE_CMD="apache2"
        APACHE_SITES="/etc/apache2/sites-available"
        APACHE_ENABLED="/etc/apache2/sites-enabled"
        APACHE_MODS="/etc/apache2/mods-enabled"
    else
        APACHE_CMD="httpd"
        APACHE_SITES="/etc/httpd/sites-available"
        APACHE_ENABLED="/etc/httpd/sites-enabled"
        APACHE_MODS="/etc/httpd/mods-enabled"
        mkdir -p "$APACHE_SITES" "$APACHE_ENABLED"
    fi
    
    # Domain name should already be set by collect_user_inputs() or command-line args
    DOMAIN_NAME=${DOMAIN_NAME:-localhost}
    
    # Enable required modules
    print_info "Enabling Apache modules..."
    a2enmod proxy proxy_http headers rewrite ssl 2>> "$LOG_FILE" || true
    
    # Create Apache configuration
    print_info "Creating Apache configuration..."
    cat > "$APACHE_SITES/kast-web.conf" << 'APACHEEOF'
<VirtualHost *:80>
    ServerName DOMAIN_PLACEHOLDER
    
    ProxyPreserveHost On
    ProxyPass /static !
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/
    
    Alias /static /opt/kast-web/app/static
    <Directory /opt/kast-web/app/static>
        Require all granted
        Options -Indexes +FollowSymLinks
    </Directory>
    
    Header always set X-Frame-Options "SAMEORIGIN"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-XSS-Protection "1; mode=block"
    
    ErrorLog /var/log/apache2/kast-web-error.log
    CustomLog /var/log/apache2/kast-web-access.log combined
</VirtualHost>
APACHEEOF
    
    # Replace domain placeholder
    sed -i "s/DOMAIN_PLACEHOLDER/$DOMAIN_NAME/" "$APACHE_SITES/kast-web.conf"
    
    # Enable site
    a2ensite kast-web.conf >> "$LOG_FILE" 2>&1
    a2dissite 000-default.conf >> "$LOG_FILE" 2>&1 || true
    
    # Test configuration
    if $APACHE_CMD -t >> "$LOG_FILE" 2>&1; then
        print_success "Apache configuration valid"
    else
        error_exit "Apache configuration test failed"
    fi
    
    # Restart Apache
    systemctl enable $APACHE_CMD >> "$LOG_FILE" 2>&1
    systemctl restart $APACHE_CMD >> "$LOG_FILE" 2>&1
    print_success "Apache configured and restarted"
}

################################################################################
# SSL Configuration
################################################################################

configure_ssl() {
    print_header "SSL Configuration"
    
    # SSL preference should already be set by collect_user_inputs() or command-line flags
    if [[ "$INSTALL_SSL" == "yes" ]]; then
        if [[ "$DOMAIN_NAME" == "localhost" || "$DOMAIN_NAME" == "127.0.0.1" ]]; then
            print_warning "Cannot install SSL for localhost. Skipping SSL configuration."
            return
        fi
        
        print_info "Installing Certbot..."
        
        if [[ "$WEB_SERVER" == "nginx" ]]; then
            apt-get install -y certbot python3-certbot-nginx >> "$LOG_FILE" 2>&1
            print_success "Certbot installed"
            
            print_info "Obtaining SSL certificate..."
            certbot --nginx -d "$DOMAIN_NAME" --non-interactive --agree-tos --register-unsafely-without-email >> "$LOG_FILE" 2>&1
            
        elif [[ "$WEB_SERVER" == "apache" ]]; then
            apt-get install -y certbot python3-certbot-apache >> "$LOG_FILE" 2>&1
            print_success "Certbot installed"
            
            print_info "Obtaining SSL certificate..."
            certbot --apache -d "$DOMAIN_NAME" --non-interactive --agree-tos --register-unsafely-without-email >> "$LOG_FILE" 2>&1
        fi
        
        print_success "SSL certificate installed"
        
        # Set up auto-renewal
        systemctl enable certbot.timer >> "$LOG_FILE" 2>&1 || true
        print_success "SSL auto-renewal configured"
    else
        print_info "Skipping SSL configuration"
    fi
}

################################################################################
# Systemd Services
################################################################################

install_systemd_services() {
    print_header "Systemd Services Installation"
    
    # Copy or create kast-web service
    if [[ -f "$INSTALL_DIR/deployment/systemd/kast-web.service" ]]; then
        cp "$INSTALL_DIR/deployment/systemd/kast-web.service" /etc/systemd/system/
        print_success "Copied kast-web.service"
    else
        # Create service file
        cat > /etc/systemd/system/kast-web.service << 'SERVICEEOF'
[Unit]
Description=KAST Web Application (Gunicorn)
After=network.target redis.service
Wants=redis.service

[Service]
Type=notify
User=www-data
Group=www-data
RuntimeDirectory=kast-web
WorkingDirectory=/opt/kast-web
Environment="PATH=/opt/kast-web/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="FLASK_ENV=production"
EnvironmentFile=/opt/kast-web/.env

ExecStartPre=/bin/mkdir -p /var/log/kast-web /var/run/kast-web
ExecStartPre=/bin/chown www-data:www-data /var/log/kast-web /var/run/kast-web

ExecStart=/opt/kast-web/venv/bin/gunicorn \
    --bind 127.0.0.1:8000 \
    --workers 4 \
    --timeout 120 \
    --access-logfile /var/log/kast-web/access.log \
    --error-logfile /var/log/kast-web/error.log \
    --log-level info \
    wsgi:app

Restart=always
RestartSec=10
KillMode=mixed
TimeoutStopSec=5

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SERVICEEOF
        print_success "Created kast-web.service"
    fi
    
    # Copy or create kast-celery service
    if [[ -f "$INSTALL_DIR/deployment/systemd/kast-celery.service" ]]; then
        cp "$INSTALL_DIR/deployment/systemd/kast-celery.service" /etc/systemd/system/
        print_success "Copied kast-celery.service"
    else
        cat > /etc/systemd/system/kast-celery.service << 'CELERYEOF'
[Unit]
Description=KAST Web Celery Worker
After=network.target redis.service
Wants=redis.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/kast-web
Environment="PATH=/opt/kast-web/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=/opt/kast-web"
EnvironmentFile=/opt/kast-web/.env

ExecStart=/opt/kast-web/venv/bin/celery -A celery_worker.celery worker \
    --loglevel=info \
    --logfile=/var/log/kast-web/celery.log

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
CELERYEOF
        print_success "Created kast-celery.service"
    fi
    
    # Reload systemd
    systemctl daemon-reload >> "$LOG_FILE" 2>&1
    
    # Enable and start services
    print_info "Enabling and starting services..."
    systemctl enable kast-web kast-celery >> "$LOG_FILE" 2>&1
    systemctl start kast-celery >> "$LOG_FILE" 2>&1
    systemctl start kast-web >> "$LOG_FILE" 2>&1
    
    # Wait a moment for services to start
    sleep 3
    
    # Check service status
    if systemctl is-active --quiet kast-web; then
        print_success "kast-web service is running"
    else
        print_error "kast-web service failed to start"
        WARNINGS+=("kast-web service is not running. Check: systemctl status kast-web")
    fi
    
    if systemctl is-active --quiet kast-celery; then
        print_success "kast-celery service is running"
    else
        print_error "kast-celery service failed to start"
        WARNINGS+=("kast-celery service is not running. Check: systemctl status kast-celery")
    fi
}

################################################################################
# Firewall Detection
################################################################################

check_firewall() {
    print_header "Firewall Detection"
    
    FIREWALL_DETECTED="no"
    
    # Check for UFW
    if command -v ufw &>/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then
        print_info "UFW firewall detected and active"
        FIREWALL_DETECTED="ufw"
        check_ufw_ports
    fi
    
    # Check for firewalld
    if command -v firewall-cmd &>/dev/null && systemctl is-active --quiet firewalld; then
        print_info "firewalld detected and active"
        FIREWALL_DETECTED="firewalld"
        check_firewalld_ports
    fi
    
    # Check for iptables
    if command -v iptables &>/dev/null && [[ "$FIREWALL_DETECTED" == "no" ]]; then
        # Check if iptables has any rules (besides default)
        RULE_COUNT=$(iptables -L -n | grep -c "^Chain\|^target")
        if [[ $RULE_COUNT -gt 6 ]]; then
            print_info "iptables rules detected"
            FIREWALL_DETECTED="iptables"
            check_iptables_ports
        fi
    fi
    
    if [[ "$FIREWALL_DETECTED" == "no" ]]; then
        print_success "No active firewall detected"
    fi
}

check_ufw_ports() {
    # Check port 80
    if ! ufw status | grep -q "80.*ALLOW"; then
        FIREWALL_WARNINGS+=("Port 80 (HTTP) may be blocked by UFW. To allow: sudo ufw allow 80/tcp")
    fi
    
    # Check port 443 if SSL is enabled
    if [[ "$INSTALL_SSL" == "yes" ]] && ! ufw status | grep -q "443.*ALLOW"; then
        FIREWALL_WARNINGS+=("Port 443 (HTTPS) may be blocked by UFW. To allow: sudo ufw allow 443/tcp")
    fi
}

check_firewalld_ports() {
    # Check port 80
    if ! firewall-cmd --list-ports | grep -q "80/tcp"; then
        FIREWALL_WARNINGS+=("Port 80 (HTTP) may be blocked by firewalld. To allow: sudo firewall-cmd --permanent --add-port=80/tcp && sudo firewall-cmd --reload")
    fi
    
    # Check port 443 if SSL is enabled
    if [[ "$INSTALL_SSL" == "yes" ]] && ! firewall-cmd --list-ports | grep -q "443/tcp"; then
        FIREWALL_WARNINGS+=("Port 443 (HTTPS) may be blocked by firewalld. To allow: sudo firewall-cmd --permanent --add-port=443/tcp && sudo firewall-cmd --reload")
    fi
}

check_iptables_ports() {
    # Check if port 80 is allowed
    if ! iptables -L -n | grep -q "ACCEPT.*tcp dpt:80"; then
        FIREWALL_WARNINGS+=("Port 80 (HTTP) may be blocked by iptables. Review your iptables rules.")
    fi
    
    # Check port 443 if SSL is enabled
    if [[ "$INSTALL_SSL" == "yes" ]] && ! iptables -L -n | grep -q "ACCEPT.*tcp dpt:443"; then
        FIREWALL_WARNINGS+=("Port 443 (HTTPS) may be blocked by iptables. Review your iptables rules.")
    fi
}

################################################################################
# Post-Installation Validation
################################################################################

validate_database_sqlite() {
    print_info "Validating SQLite database configuration..."
    local validation_failed=0
    
    # Check database file location
    local db_path="/var/lib/kast-web/kast.db"
    if [[ -f "$db_path" ]]; then
        print_success "Database file exists at correct location: $db_path"
        
        # Check ownership
        local db_owner=$(stat -c '%U:%G' "$db_path" 2>/dev/null)
        if [[ "$db_owner" == "$SERVICE_USER:$SERVICE_USER" ]]; then
            print_success "Database ownership correct: $db_owner"
        else
            print_error "Database ownership incorrect: $db_owner (expected: $SERVICE_USER:$SERVICE_USER)"
            validation_failed=1
        fi
        
        # Check permissions (should be at least readable by owner)
        local db_perms=$(stat -c '%a' "$db_path" 2>/dev/null)
        if [[ "$db_perms" =~ ^[6-7][0-7][0-7]$ ]] || [[ "$db_perms" =~ ^[0-7][4-7][0-7]$ ]]; then
            print_success "Database permissions OK: $db_perms"
        else
            print_warning "Database permissions may be too restrictive: $db_perms"
        fi
    else
        print_error "Database file not found at $db_path"
        validation_failed=1
        return $validation_failed
    fi
    
    # Warn about old database location
    if [[ -f "/root/kast-web/db/kast.db" ]]; then
        print_warning "Old database found at /root/kast-web/db/kast.db"
        WARNINGS+=("Remove old database file: sudo rm -rf /root/kast-web")
    fi
    
    # Validate admin user exists with proper configuration
    if command -v sqlite3 &>/dev/null; then
        print_info "Validating admin user in database..."
        
        # Check if users table exists
        local table_count=$(sqlite3 "$db_path" "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='users';" 2>/dev/null)
        if [[ "$table_count" == "1" ]]; then
            print_success "Users table exists in database"
            
            # Check if admin user exists
            local admin_count=$(sqlite3 "$db_path" "SELECT count(*) FROM users WHERE role='admin' AND is_active=1;" 2>/dev/null)
            if [[ "$admin_count" -gt 0 ]]; then
                print_success "Active admin user found in database"
                
                # Validate password hash
                local hash_info=$(sqlite3 "$db_path" "SELECT username, length(password_hash), substr(password_hash, 1, 4) FROM users WHERE role='admin' AND is_active=1 LIMIT 1;" 2>/dev/null)
                
                if [[ -n "$hash_info" ]]; then
                    local username=$(echo "$hash_info" | cut -d'|' -f1)
                    local hash_length=$(echo "$hash_info" | cut -d'|' -f2)
                    local hash_prefix=$(echo "$hash_info" | cut -d'|' -f3)
                    
                    print_success "Admin user: $username"
                    
                    # Bcrypt hashes are 60 characters and start with $2a$, $2b$, or $2y$
                    if [[ "$hash_length" == "60" ]] && [[ "$hash_prefix" =~ ^\$2[aby]\$ ]]; then
                        print_success "Password hash valid (length: $hash_length, format: bcrypt)"
                    elif [[ "$hash_length" -gt 0 ]]; then
                        print_warning "Password hash present but format may be non-standard (length: $hash_length)"
                    else
                        print_error "Password hash is empty or invalid"
                        validation_failed=1
                    fi
                else
                    print_error "Could not validate password hash"
                    validation_failed=1
                fi
            else
                print_error "No active admin user found in database"
                validation_failed=1
            fi
        else
            print_error "Users table not found in database"
            validation_failed=1
        fi
        
        # Validate other critical tables exist
        local critical_tables=("scans" "scan_results" "audit_logs" "system_settings")
        local missing_tables=()
        
        for table in "${critical_tables[@]}"; do
            local exists=$(sqlite3 "$db_path" "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='$table';" 2>/dev/null)
            if [[ "$exists" != "1" ]]; then
                missing_tables+=("$table")
            fi
        done
        
        if [[ ${#missing_tables[@]} -eq 0 ]]; then
            print_success "All critical database tables exist"
        else
            print_warning "Some database tables may be missing: ${missing_tables[*]}"
        fi
    else
        print_warning "sqlite3 command not available, skipping detailed database validation"
        WARNINGS+=("Install sqlite3 for detailed database validation: sudo apt-get install sqlite3")
    fi
    
    return $validation_failed
}

validate_installation() {
    print_header "Installation Validation"
    
    local validation_failed=0
    
    # Check Redis
    if redis-cli ping &>/dev/null; then
        print_success "Redis is responding"
    else
        print_error "Redis is not responding"
        validation_failed=1
    fi
    
    # Check Celery worker
    if systemctl is-active --quiet kast-celery; then
        print_success "Celery worker is running"
    else
        print_error "Celery worker is not running"
        validation_failed=1
    fi
    
    # Check Gunicorn
    if systemctl is-active --quiet kast-web; then
        print_success "Gunicorn is running"
    else
        print_error "Gunicorn is not running"
        validation_failed=1
    fi
    
    # Check web server
    if systemctl is-active --quiet nginx || systemctl is-active --quiet apache2; then
        print_success "Web server is running"
    else
        print_error "Web server is not running"
        validation_failed=1
    fi
    
    # Check if application responds
    sleep 2
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 | grep -q "200\|302"; then
        print_success "Application is responding"
    else
        print_warning "Application may not be responding correctly"
    fi
    
    # Check database connection
    cd "$INSTALL_DIR"
    source "$VENV_DIR/bin/activate"
    if python3 -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.engine.connect()" 2>/dev/null; then
        print_success "Database connection successful"
    else
        print_error "Database connection failed"
        validation_failed=1
    fi
    
    # Check KAST CLI integration
    if $KAST_CLI_PATH --version &>/dev/null; then
        print_success "KAST CLI is accessible"
    else
        print_warning "KAST CLI may not be accessible to the application"
    fi
    
    # SQLite-specific database validation
    if [[ "$DATABASE_TYPE" == "sqlite" ]]; then
        echo ""
        if ! validate_database_sqlite; then
            validation_failed=1
        fi
    fi
    
    return $validation_failed
}

################################################################################
# Installation Report
################################################################################

generate_report() {
    print_header "Installation Report"
    
    # Determine access URL
    if [[ "$INSTALL_SSL" == "yes" ]]; then
        ACCESS_URL="https://$DOMAIN_NAME"
    else
        ACCESS_URL="http://$DOMAIN_NAME"
    fi
    
    echo -e "${GREEN}${BOLD}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║                                                       ║"
    echo "║   KAST-Web Installation Completed Successfully!       ║"
    echo "║                                                       ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "\n${CYAN}${BOLD}Installation Details:${NC}"
    echo -e "  Installation Directory: ${GREEN}$INSTALL_DIR${NC}"
    echo -e "  Database Type: ${GREEN}$DATABASE_TYPE${NC}"
    if [[ "$DATABASE_TYPE" == "sqlite" ]]; then
        echo -e "  Database Location: ${GREEN}/var/lib/kast-web/kast.db${NC}"
    else
        echo -e "  Database Name: ${GREEN}$DB_NAME${NC}"
    fi
    echo -e "  Web Server: ${GREEN}$WEB_SERVER${NC}"
    echo -e "  Domain: ${GREEN}$DOMAIN_NAME${NC}"
    echo -e "  SSL Enabled: ${GREEN}$INSTALL_SSL${NC}"
    
    echo -e "\n${CYAN}${BOLD}File Locations:${NC}"
    echo -e "  ${BOLD}Application Files:${NC}"
    echo -e "    Installation:        ${GREEN}$INSTALL_DIR${NC}"
    echo -e "    Virtual Environment: ${GREEN}$INSTALL_DIR/venv${NC}"
    echo -e "    Configuration:       ${GREEN}$INSTALL_DIR/.env${NC}"
    echo -e "    Static Files:        ${GREEN}$INSTALL_DIR/app/static${NC}"
    echo -e ""
    echo -e "  ${BOLD}Data Files:${NC}"
    if [[ "$DATABASE_TYPE" == "sqlite" ]]; then
        echo -e "    Database:            ${GREEN}/var/lib/kast-web/kast.db${NC}"
    fi
    echo -e "    Scan Results:        ${GREEN}/var/lib/kast-web/results${NC}"
    echo -e ""
    echo -e "  ${BOLD}Log Files:${NC}"
    echo -e "    Application Logs:    ${GREEN}/var/log/kast-web/${NC}"
    echo -e "      - access.log       (Web access logs)"
    echo -e "      - error.log        (Application errors)"
    echo -e "      - celery.log       (Background task processing)"
    echo -e "    PID Files:           ${GREEN}/var/run/kast-web/${NC}"
    
    echo -e "\n${CYAN}${BOLD}Port Configuration:${NC}"
    if [[ "$WEB_SERVER" == "nginx" ]]; then
        echo -e "  Nginx (Public):       Port 80 (HTTP)"
        [[ "$INSTALL_SSL" == "yes" ]] && echo -e "  Nginx (Public):       Port 443 (HTTPS)"
    elif [[ "$WEB_SERVER" == "apache" ]]; then
        echo -e "  Apache (Public):      Port 80 (HTTP)"
        [[ "$INSTALL_SSL" == "yes" ]] && echo -e "  Apache (Public):      Port 443 (HTTPS)"
    fi
    echo -e "  Gunicorn (Internal):  Port 8000"
    echo -e "  Redis (Internal):     Port 6379"
    
    echo -e "\n${CYAN}${BOLD}Access Information:${NC}"
    echo -e "  URL: ${GREEN}${ACCESS_URL}${NC}"
    echo -e "  Admin Username: ${GREEN}${ADMIN_USERNAME}${NC}"
    echo -e "  Admin Email: ${GREEN}${ADMIN_EMAIL}${NC}"
    
    echo -e "\n${CYAN}${BOLD}Service Status:${NC}"
    systemctl is-active --quiet redis-server && echo -e "  Redis:        ${GREEN}RUNNING${NC}" || echo -e "  Redis:        ${RED}STOPPED${NC}"
    systemctl is-active --quiet kast-celery && echo -e "  Celery:       ${GREEN}RUNNING${NC}" || echo -e "  Celery:       ${RED}STOPPED${NC}"
    systemctl is-active --quiet kast-web && echo -e "  Gunicorn:     ${GREEN}RUNNING${NC}" || echo -e "  Gunicorn:     ${RED}STOPPED${NC}"
    systemctl is-active --quiet nginx && echo -e "  Nginx:        ${GREEN}RUNNING${NC}" || systemctl is-active --quiet apache2 && echo -e "  Apache:       ${GREEN}RUNNING${NC}" || echo -e "  Web Server:   ${RED}STOPPED${NC}"
    
    # Display warnings
    if [[ ${#WARNINGS[@]} -gt 0 ]]; then
        echo -e "\n${YELLOW}${BOLD}⚠ Warnings:${NC}"
        for warning in "${WARNINGS[@]}"; do
            echo -e "  ${YELLOW}•${NC} $warning"
        done
    fi
    
    # Display firewall warnings
    if [[ ${#FIREWALL_WARNINGS[@]} -gt 0 ]]; then
        echo -e "\n${YELLOW}${BOLD}⚠ Firewall Configuration Required:${NC}"
        for fw_warning in "${FIREWALL_WARNINGS[@]}"; do
            echo -e "  ${YELLOW}•${NC} $fw_warning"
        done
    fi
    
    echo -e "\n${CYAN}${BOLD}KAST CLI Integration:${NC}"
    if [[ -d /var/log/kast ]]; then
        echo -e "  ${BOLD}Log Directory Permissions:${NC}"
        echo -e "    • Location:           ${GREEN}/var/log/kast${NC}"
        echo -e "    • Group:              ${GREEN}kast${NC} (shared between users and www-data)"
        echo -e "    • Permissions:        ${GREEN}2775${NC} (rwxrwsr-x with setgid bit)"
        echo -e "    • Both the KAST user and www-data can write to KAST logs"
        echo -e ""
    fi
    
    echo -e "\n${CYAN}${BOLD}Getting Started:${NC}"
    echo -e "  ${BOLD}Important:${NC} Celery worker must be running for scans to work!"
    echo -e "  The Celery worker processes scan tasks asynchronously in the background."
    echo -e ""
    echo -e "  ${BOLD}Managing Services:${NC}"
    echo -e "    • Check all services:    sudo systemctl status kast-web kast-celery redis-server"
    echo -e "    • Restart web app:       sudo systemctl restart kast-web"
    echo -e "    • Restart Celery:        sudo systemctl restart kast-celery"
    echo -e "    • View web app logs:     sudo journalctl -u kast-web -f"
    echo -e "    • View Celery logs:      sudo journalctl -u kast-celery -f"
    echo -e "    • View all logs:         sudo tail -f /var/log/kast-web/*.log"
    echo -e ""
    echo -e "  ${BOLD}Troubleshooting:${NC}"
    echo -e "    • If scans fail:         Check Celery service is running"
    echo -e "    • If pages don't load:   Check Nginx/Apache and Gunicorn services"
    echo -e "    • For detailed errors:   Check $LOG_FILE"
    echo -e ""
    echo -e "  ${BOLD}Configuration Files:${NC}"
    echo -e "    • Application:           $INSTALL_DIR/.env"
    echo -e "    • Web server:            /etc/$WEB_SERVER/sites-available/kast-web"
    echo -e "    • Systemd services:      /etc/systemd/system/kast-*.service"
    
    echo -e "\n${CYAN}${BOLD}Next Steps:${NC}"
    echo -e "  1. Visit ${GREEN}${ACCESS_URL}${NC} in your browser"
    echo -e "  2. Log in with your admin credentials"
    echo -e "  3. Configure any additional settings in the admin panel"
    echo -e "  4. Start a scan - Celery will process it automatically!"
    
    if [[ ${#FIREWALL_WARNINGS[@]} -gt 0 ]]; then
        echo -e "\n  ${YELLOW}⚠ Don't forget to configure your firewall!${NC}"
    fi
    
    echo -e "\n${GREEN}Installation log saved to: $LOG_FILE${NC}\n"
}

################################################################################
# Main Installation Flow
################################################################################

main() {
    # Parse command-line arguments
    parse_arguments "$@"
    
    # Print banner
    echo -e "${CYAN}${BOLD}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║                                                       ║"
    echo "║          KAST-Web Installation Script v1.0            ║"
    echo "║                                                       ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}\n"
    
    # Initialize log file
    touch "$LOG_FILE"
    log "KAST-Web Installation Started"
    log "Command: $0 $*"
    
    # Pre-installation checks
    check_root
    check_os
    check_disk_space
    check_kast_cli
    configure_kast_permissions
    configure_security_tool_configs
    
    # Collect all user inputs upfront (interactive mode only)
    collect_user_inputs
    
    # Check for existing installation (now uses pre-collected choice)
    check_existing_installation
    
    # System dependencies
    install_system_dependencies
    
    # Database configuration
    configure_database
    
    # Application setup
    setup_application
    initialize_database
    create_admin_user
    
    # Web server configuration
    detect_web_server
    
    if [[ "$WEB_SERVER" == "nginx" ]]; then
        configure_nginx
    elif [[ "$WEB_SERVER" == "apache" ]]; then
        configure_apache
    else
        error_exit "Unknown web server: $WEB_SERVER"
    fi
    
    # SSL configuration
    configure_ssl
    
    # Systemd services
    install_systemd_services
    
    # Firewall check
    check_firewall
    
    # Validate installation
    validate_installation
    
    # Generate report
    generate_report
    
    log "KAST-Web Installation Completed Successfully"
}

# Run main function
main "$@"
