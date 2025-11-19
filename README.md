# KAST Web

A web-based interface for the Kali Automated Scan Tool (KAST), providing an intuitive way to configure, execute, and manage security scans through your browser. Features asynchronous scan execution with real-time progress tracking and a RESTful API.

## Features

- **Easy Scan Configuration**: Web form interface for setting up scans
- **Asynchronous Execution**: Scans run in background using Celery task queue
- **Real-time Progress Tracking**: Monitor scan progress with live status updates
- **Plugin Selection**: Choose which security tools to run
- **Scan History**: Track all your scans with filtering and search capabilities
- **Report Viewing**: View and download HTML reports directly in the browser
- **Scan Management**: Re-run or delete scans with ease
- **RESTful API**: Programmatic access to scan data with status polling
- **Production Ready**: Complete deployment setup with Nginx, Gunicorn, and systemd

## Technology Stack

### Backend
- **Flask** - Python web framework
- **SQLAlchemy** - Database ORM
- **SQLite** - Default database (PostgreSQL/MySQL supported)
- **WTForms** - Form handling and validation
- **Celery** - Asynchronous task queue
- **Redis** - Message broker for Celery
- **Flask-SocketIO** - Real-time communication support
- **Gunicorn** - WSGI HTTP server for production

### Frontend
- **Bootstrap 5** - UI framework
- **Bootstrap Icons** - Icon library
- **Jinja2** - Template engine
- **JavaScript** - Client-side interactivity

## Installation

### Prerequisites

- Python 3.8 or higher
- Redis server (for async task processing)
- KAST CLI tool installed with launcher script at `/usr/local/bin/kast`
- pip (Python package manager)

### Development Setup

1. **Clone or navigate to the project directory:**
   ```bash
   cd /opt/kast-web
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Linux/Mac
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install and start Redis:**
   ```bash
   # On Ubuntu/Debian
   sudo apt install redis-server
   sudo systemctl start redis-server
   sudo systemctl enable redis-server
   
   # Verify Redis is running
   redis-cli ping  # Should return "PONG"
   ```

5. **Configure environment variables (optional):**
   ```bash
   cp .env.example .env
   # Edit .env with your preferred settings
   ```

6. **Initialize the database:**
   The database will be automatically created when you first run the application.

## Running the Application

### Quick Start (Development)

Use the provided start script:

```bash
./scripts/start.sh
```

### Manual Start (Development)

KAST Web requires two components to be running:

**Terminal 1 - Start Celery Worker:**
```bash
source venv/bin/activate
celery -A celery_worker.celery worker --loglevel=info
```

**Terminal 2 - Start Flask Application:**
```bash
source venv/bin/activate
python3 run.py
```

The application will be available at `http://localhost:5000`

### Helper Scripts

- **`./scripts/start.sh`** - Start Flask development server
- **`./scripts/start_async.sh`** - Interactive script to start all components
- **`./scripts/verify_celery.sh`** - Verify Celery configuration

### Production Deployment

For production deployment with Nginx, Gunicorn, and systemd services, see the comprehensive guides:

- **Quick Start**: [`deployment/QUICK_START.md`](deployment/QUICK_START.md)
- **Full Guide**: [`docs/PRODUCTION_DEPLOYMENT.md`](docs/PRODUCTION_DEPLOYMENT.md)

Quick production install:

```bash
# Install production dependencies
pip install -r requirements-production.txt

# Setup systemd services
sudo cp deployment/systemd/kast-web.service /etc/systemd/system/
sudo cp deployment/systemd/kast-celery.service /etc/systemd/system/

# Setup Nginx
sudo cp deployment/nginx/kast-web.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/kast-web.conf /etc/nginx/sites-enabled/

# Start services
sudo systemctl enable --now redis-server kast-web kast-celery nginx
```

## Configuration

Configuration is managed through `config.py` and environment variables:

- **SECRET_KEY**: Flask secret key (set via environment variable in production)
- **DATABASE_URL**: Database connection string (default: SQLite in `~/kast-web/db/`)
- **KAST_CLI_PATH**: Path to KAST CLI launcher script (default: `/usr/local/bin/kast`)
- **KAST_RESULTS_DIR**: Directory for scan results (default: `~/kast_results/`)
- **CELERY_BROKER_URL**: Redis connection for Celery (default: `redis://localhost:6379/0`)
- **CELERY_RESULT_BACKEND**: Redis backend for task results (default: `redis://localhost:6379/0`)

### Configuration Profiles

The application supports multiple configuration profiles:
- **development** (default) - Debug mode enabled
- **production** - Optimized for production
- **testing** - In-memory database for tests

Set the profile using the `FLASK_ENV` environment variable.

## Project Structure

```
kast-web/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── models.py                # Database models (Scan, ScanResult)
│   ├── forms.py                 # WTForms for scan configuration
│   ├── tasks.py                 # Celery tasks for async execution
│   ├── utils.py                 # Helper functions
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── main.py              # Main web routes
│   │   ├── scans.py             # Scan management routes
│   │   └── api.py               # RESTful API endpoints
│   ├── templates/               # Jinja2 templates
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── scan_detail.html
│   │   ├── scan_history.html
│   │   ├── scan_files.html
│   │   ├── report_viewer.html
│   │   └── about.html
│   └── static/                  # Static assets
│       ├── css/
│       │   └── custom.css
│       └── js/
│           ├── main.js
│           └── report-viewer.js
├── deployment/
│   ├── QUICK_START.md           # Quick deployment guide
│   ├── .env.production          # Production environment template
│   ├── nginx/
│   │   └── kast-web.conf        # Nginx configuration
│   └── systemd/
│       ├── kast-web.service     # Gunicorn systemd service
│       └── kast-celery.service  # Celery systemd service
├── docs/
│   ├── PRODUCTION_DEPLOYMENT.md # Comprehensive deployment guide
│   ├── ASYNC_SETUP.md           # Async/Celery setup guide
│   └── ...                      # Additional documentation
├── scripts/
│   ├── start.sh                 # Start Flask dev server
│   ├── start_async.sh           # Start all components interactively
│   └── verify_celery.sh         # Verify Celery setup
├── config.py                    # Application configuration
├── celery_worker.py             # Celery worker initialization
├── gunicorn_config.py           # Gunicorn configuration
├── wsgi.py                      # WSGI entry point
├── run.py                       # Development server
├── migrate_db.py                # Database migration utility
├── requirements.txt             # Development dependencies
├── requirements-production.txt  # Production dependencies
├── .env.example                 # Environment variables template
├── .gitignore
└── README.md                    # This file
```

## API Endpoints

KAST Web provides a comprehensive RESTful API:

### Scans

- **`GET /api/scans`** - List all scans with pagination
  - Query params: `page`, `per_page`, `status`
  - Returns: List of scans with metadata

- **`GET /api/scans/<id>`** - Get detailed scan information
  - Returns: Scan details and all plugin results

- **`GET /api/scans/<id>/status`** - Get real-time scan status (for polling)
  - Returns: Current scan status and per-plugin progress
  - Useful for monitoring running scans

### Plugins

- **`GET /api/plugins`** - List available KAST plugins
  - Returns: Plugin names and descriptions

### Statistics

- **`GET /api/stats`** - Get scan statistics
  - Returns: Total, completed, failed, and running scan counts

### Example API Usage

```bash
# Get all scans
curl http://localhost:5000/api/scans

# Get specific scan with results
curl http://localhost:5000/api/scans/1

# Poll scan status (for monitoring progress)
curl http://localhost:5000/api/scans/1/status

# Get available plugins
curl http://localhost:5000/api/plugins

# Get statistics
curl http://localhost:5000/api/stats

# Get scans by status
curl http://localhost:5000/api/scans?status=completed
```

## Usage

### Running a Scan

1. **Navigate to the home page** at `http://localhost:5000`
2. **Configure a new scan:**
   - Enter target domain (e.g., `example.com`)
   - Select scan mode:
     - **Passive**: Non-intrusive reconnaissance only
     - **Active**: Includes active scanning techniques
   - Choose specific plugins (optional - leave empty for all plugins)
   - Configure options:
     - **Parallel execution**: Run plugins simultaneously
     - **Verbose output**: Enable detailed logging
     - **Dry run**: Preview without executing
3. **Submit the scan** 
   - Scan executes asynchronously via Celery
   - Redirects to scan detail page with real-time progress
4. **Monitor progress**
   - Status updates automatically via polling
   - See individual plugin status and findings count
5. **View results**
   - Access detailed reports when complete
   - Download output files
   - View parsed findings

### Scan History

- View all past scans at `/scans/history`
- Filter by status (pending, running, completed, failed)
- Search by target domain
- Quick actions: re-run, view details, delete

### Viewing Reports

- Click "View Report" on completed scans
- Interactive HTML report viewer
- View individual plugin outputs
- Access raw JSON data files

## Database

### Location

The SQLite database is stored at `~/kast-web/db/kast.db` by default. The directory is automatically created if it doesn't exist.

For production deployments, PostgreSQL or MySQL is recommended. See [`docs/PRODUCTION_DEPLOYMENT.md`](docs/PRODUCTION_DEPLOYMENT.md) for database configuration.

### Database Schema

**Scans Table:**
- Stores scan configuration and metadata
- Tracks scan status (pending, running, completed, failed)
- Links to Celery task for async execution
- Records start time, completion time, and duration
- Stores output directory path and error messages

**ScanResults Table:**
- Stores individual plugin results
- Links to parent scan via foreign key
- Tracks plugin status and findings count
- Stores paths to raw and processed output files
- Records execution timestamp

### Database Migrations

Use the provided migration utility:

```bash
python3 migrate_db.py
```

## Asynchronous Architecture

KAST Web uses Celery for asynchronous task processing, allowing scans to run in the background without blocking the web interface.

### Components

1. **Flask Application** - Handles web requests and renders UI
2. **Celery Worker** - Executes scan tasks asynchronously
3. **Redis** - Message broker connecting Flask and Celery
4. **Database** - Stores scan metadata and results

### Task Flow

1. User submits scan via web form
2. Flask creates database record with "pending" status
3. Celery task is queued via Redis
4. Celery worker picks up task and executes KAST CLI
5. Task updates database status to "running"
6. Results are parsed and stored as they become available
7. Task updates status to "completed" or "failed"
8. User sees real-time updates via status polling

### Monitoring Tasks

Check Celery worker status:
```bash
celery -A celery_worker.celery inspect active
celery -A celery_worker.celery inspect stats
```

View Celery logs:
```bash
# Development
celery -A celery_worker.celery worker --loglevel=info

# Production (systemd)
sudo journalctl -u kast-celery -f
```

## Troubleshooting

### Common Issues

**Issue: Scans stuck in "pending" status**
- **Cause**: Celery worker not running
- **Solution**: Start Celery worker: `celery -A celery_worker.celery worker --loglevel=info`
- **Verify**: Check Redis connection: `redis-cli ping`

**Issue: "Connection refused" errors**
- **Cause**: Redis not running
- **Solution**: Start Redis: `sudo systemctl start redis-server`
- **Verify**: `redis-cli ping` should return "PONG"

**Issue: Plugins not showing up**
- **Cause**: KAST CLI not found or not configured
- **Solution**: 
  - Verify KAST CLI exists: `ls -la /usr/local/bin/kast`
  - Check configuration in `config.py` or `.env`
  - Test KAST CLI: `kast --list-plugins`

**Issue: Scans failing to execute**
- **Cause**: Multiple possible causes
- **Solutions**:
  - Check KAST CLI is executable: `chmod +x /usr/local/bin/kast`
  - Verify target domain is valid
  - Check Celery worker logs for errors
  - Ensure required security tools are installed
  - Verify output directory is writable

**Issue: Database errors**
- **Cause**: Database file or directory issues
- **Solutions**:
  - Ensure `~/kast-web/db/` directory exists and is writable
  - Check database file permissions
  - Reset database: `rm ~/kast-web/db/kast.db` (WARNING: deletes all data)
  - Restart application to recreate database

**Issue: Permission errors**
- **Solutions**:
  - Fix project permissions: `chmod -R 755 /opt/kast-web`
  - Fix output directory: `chmod -R 755 ~/kast_results`
  - In production, ensure www-data user has access

**Issue: Real-time updates not working**
- **Cause**: Status polling not functioning
- **Solutions**:
  - Check browser console for JavaScript errors
  - Verify `/api/scans/<id>/status` endpoint is accessible
  - Ensure scan status page JavaScript is loaded

For additional troubleshooting, check:
- [`docs/STATUS_DEBUGGING.md`](docs/STATUS_DEBUGGING.md) - Status tracking debugging
- [`docs/PRODUCTION_DEPLOYMENT.md`](docs/PRODUCTION_DEPLOYMENT.md) - Production issues

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run tests
pytest

# Run with coverage
pytest --cov=app tests/
```

### Code Style

This project follows PEP 8 style guidelines. Use tools like `black` and `flake8`:

```bash
pip install black flake8
black .
flake8 app/
```

### Development Tips

- Use `FLASK_ENV=development` for auto-reload
- Enable verbose logging with `FLASK_DEBUG=1`
- Check Celery worker output for task debugging
- Use Redis CLI to inspect queued tasks: `redis-cli`
- Monitor database changes: `sqlite3 ~/kast-web/db/kast.db`

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Write/update tests as needed
5. Ensure code follows PEP 8 style guidelines
6. Test your changes thoroughly
7. Update documentation if needed
8. Submit a pull request with a clear description

## Security Considerations

- Always use HTTPS in production deployments
- Set a strong, unique `SECRET_KEY` in production
- Restrict database access to localhost
- Keep dependencies updated regularly
- Use firewall rules to limit network access
- Regularly backup your database
- Monitor logs for suspicious activity
- Follow principle of least privilege for service accounts

See [`docs/PRODUCTION_DEPLOYMENT.md`](docs/PRODUCTION_DEPLOYMENT.md) for comprehensive security best practices.

## Documentation

Additional documentation is available in the `docs/` directory:

- **[PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md)** - Complete production deployment guide
- **[ASYNC_SETUP.md](docs/ASYNC_SETUP.md)** - Async/Celery setup and configuration
- **[QUICK_START.md](deployment/QUICK_START.md)** - Quick production deployment
- **STATUS_DEBUGGING.md** - Debugging scan status issues
- **PLUGIN_RESULTS_FIX.md** - Plugin result parsing fixes
- **OUTPUT_FILES_FEATURE.md** - Output file handling

## Future Enhancements

Planned features for future releases:

- **User Authentication**: Multi-user support with role-based access control
- **WebSocket Integration**: Full real-time updates (Flask-SocketIO already included)
- **Scan Scheduling**: Automated recurring scans with cron-like scheduling
- **Scan Templates**: Save and reuse common scan configurations
- **Scan Comparison**: Compare results across multiple scans
- **Email Notifications**: Alert on scan completion or failures
- **Advanced Analytics**: Trend analysis and vulnerability tracking dashboards
- **Export Functionality**: Export results to various formats (PDF, CSV, JSON)
- **API Authentication**: Token-based API access for external integrations
- **Plugin Management**: Web interface for managing KAST plugins
- **Scan Queuing**: Priority-based scan queue management
- **Resource Monitoring**: Track system resource usage during scans

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues, questions, or contributions:
- Check existing documentation in `docs/` directory
- Review troubleshooting section above
- Open an issue on the project repository
- Refer to the main KAST project documentation

## Acknowledgments

- Built with Flask and Bootstrap
- Integrates with KAST CLI tool
- Powered by Celery for asynchronous task processing
- Inspired by the need for user-friendly security scanning interfaces
