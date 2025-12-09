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
                shift
                ;;
            --no-ssl)
                INSTALL_SSL="no"
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
        
        echo ""
        echo "Choose an action:"
        echo "  [1] Backup and upgrade existing installation"
        echo "  [2] Fresh install (remove existing installation)"
        echo "  [3] Abort installation"
        echo ""
        read -p "Enter choice [1-3]: " -r choice
        
        case $choice in
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
            3)
                print_info "Installation aborted by user"
                exit 0
                ;;
            *)
                error_exit "Invalid choice"
                ;;
        esac
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
    
    if [[ "$NON_INTERACTIVE" == "no" && -z "$DATABASE_TYPE" ]]; then
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
    DB_DIR="$HOME/kast-web/db"
    mkdir -p "$DB_DIR"
    DATABASE_URL="sqlite:///$DB_DIR/kast.db"
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
    mkdir -p "$HOME/kast_results"
    
    # Set ownership
    chown -R $SERVICE_USER:$SERVICE_USER /var/log/kast-web
    chown -R $SERVICE_USER:$SERVICE_USER /var/run/kast-web
    
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
KAST_RESULTS_DIR=$HOME/kast_results
EOF
    
    chmod 600 "$INSTALL_DIR/.env"
    print_success "Configuration file created"
}

initialize_database() {
    print_header "Database Initialization"
    
    cd "$INSTALL_DIR" || error_exit "Failed to change to installation directory"
    source "$VENV_DIR/bin/activate" || error_exit "Failed to activate virtual environment"
    
    # Set PYTHONPATH so migrations can import app module
    export PYTHONPATH="$INSTALL_DIR"
    
    # Run database migrations if they exist
    if [[ -d "$INSTALL_DIR/utils" ]]; then
        print_info "Running database migrations..."
        
        for migration in "$INSTALL_DIR"/utils/migrate*.py; do
            if [[ -f "$migration" ]]; then
                print_info "Running migration: $(basename "$migration")"
                python3 "$migration" >> "$LOG_FILE" 2>&1 || true
            fi
        done
    fi
    
    # Initialize database tables
    print_info "Initializing database tables..."
    if python3 << 'EOF' >> "$LOG_FILE" 2>&1
from app import create_app, db
app = create_app()
with app.app_context():
    db.create_all()
    print("Database tables created successfully")
EOF
    then
        print_success "Database initialized"
    else
        error_exit "Database initialization failed. Check $LOG_FILE for details."
    fi
}

create_admin_user() {
    print_header "Admin User Creation"
    
    cd "$INSTALL_DIR" || error_exit "Failed to change to installation directory"
    source "$VENV_DIR/bin/activate" || error_exit "Failed to activate virtual environment"
    
    # Prompt for admin credentials if not provided
    if [[ "$NON_INTERACTIVE" == "no" ]]; then
        if [[ -z "$ADMIN_USERNAME" ]]; then
            read -p "Admin username (3-80 characters): " ADMIN_USERNAME
        fi
        
        if [[ -z "$ADMIN_EMAIL" ]]; then
            read -p "Admin email: " ADMIN_EMAIL
        fi
        
        if [[ -z "$ADMIN_FIRST_NAME" ]]; then
            read -p "Admin first name (optional): " ADMIN_FIRST_NAME
        fi
        
        if [[ -z "$ADMIN_LAST_NAME" ]]; then
            read -p "Admin last name (optional): " ADMIN_LAST_NAME
        fi
        
        if [[ -z "$ADMIN_PASSWORD" ]]; then
            read -s -p "Admin password (min 8 characters): " ADMIN_PASSWORD
            echo ""
            read -s -p "Confirm password: " ADMIN_PASSWORD_CONFIRM
            echo ""
            
            if [[ "$ADMIN_PASSWORD" != "$ADMIN_PASSWORD_CONFIRM" ]]; then
                error_exit "Passwords do not match"
            fi
        fi
    fi
    
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
    python3 << EOF >> "$LOG_FILE" 2>&1
from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    # Check if user already exists
    existing_user = User.query.filter_by(username='$ADMIN_USERNAME').first()
    if existing_user:
        print("User already exists, skipping creation")
    else:
        admin_user = User(
            username='$ADMIN_USERNAME',
            email='$ADMIN_EMAIL',
            first_name='$ADMIN_FIRST_NAME' if '$ADMIN_FIRST_NAME' else None,
            last_name='$ADMIN_LAST_NAME' if '$ADMIN_LAST_NAME' else None,
            role='admin',
            is_active=True
        )
        admin_user.set_password('$ADMIN_PASSWORD')
        db.session.add(admin_user)
        db.session.commit()
        print("Admin user created successfully")
EOF
    
    print_success "Admin user created: $ADMIN_USERNAME"
}

################################################################################
# Web Server Configuration
################################################################################

detect_web_server() {
    print_header "Web Server Detection"
    
    if [[ -n "$WEB_SERVER" ]]; then
        print_info "Web server specified: $WEB_SERVER"
        return
    fi
    
    # Check for Apache
    if command -v apache2 &>/dev/null || command -v httpd &>/dev/null; then
        print_success "Apache detected"
        APACHE_INSTALLED="yes"
    fi
    
    # Check for Nginx
    if command -v nginx &>/dev/null; then
        print_success "Nginx detected"
        NGINX_INSTALLED="yes"
    fi
    
    # Prompt user if both or neither are installed
    if [[ "$APACHE_INSTALLED" == "yes" && "$NGINX_INSTALLED" == "yes" ]]; then
        if [[ "$NON_INTERACTIVE" == "no" ]]; then
            echo ""
            echo "Both Apache and Nginx are installed. Which would you like to use?"
            echo "  [1] Nginx (recommended)"
            echo "  [2] Apache"
            read -p "Enter choice [1-2]: " -r ws_choice
            
            case $ws_choice in
                1) WEB_SERVER="nginx" ;;
                2) WEB_SERVER="apache" ;;
                *) WEB_SERVER="nginx" ;;
            esac
        else
            WEB_SERVER="nginx"
        fi
    elif [[ "$APACHE_INSTALLED" == "yes" ]]; then
        WEB_SERVER="apache"
    elif [[ "$NGINX_INSTALLED" == "yes" ]]; then
        WEB_SERVER="nginx"
    else
        print_info "No web server detected. Installing Nginx..."
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
    
    # Get domain name
    if [[ -z "$DOMAIN_NAME" && "$NON_INTERACTIVE" == "no" ]]; then
        read -p "Enter domain name (or press Enter for localhost): " DOMAIN_NAME
        DOMAIN_NAME=${DOMAIN_NAME:-localhost}
    fi
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
    
    # Get domain name
    if [[ -z "$DOMAIN_NAME" && "$NON_INTERACTIVE" == "no" ]]; then
        read -p "Enter domain name (or press Enter for localhost): " DOMAIN_NAME
        DOMAIN_NAME=${DOMAIN_NAME:-localhost}
    fi
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
    
    if [[ "$INSTALL_SSL" == "no" && "$NON_INTERACTIVE" == "no" ]]; then
        read -p "Install Let's Encrypt SSL certificate? (y/N): " -r ssl_choice
        if [[ "$ssl_choice" =~ ^[Yy]$ ]]; then
            INSTALL_SSL="yes"
        fi
    fi
    
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
Environment="PATH=/opt/kast-web/venv/bin"
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
Environment="PATH=/opt/kast-web/venv/bin"
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
    echo -e "  Database Type: $DATABASE_TYPE"
    if [[ "$DATABASE_TYPE" == "sqlite" ]]; then
        echo -e "  Database Location: $DB_DIR/kast.db"
    else
        echo -e "  Database Name: $DB_NAME"
    fi
    echo -e "  Web Server: $WEB_SERVER"
    echo -e "  Domain: $DOMAIN_NAME"
    echo -e "  SSL Enabled: $INSTALL_SSL"
    
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
