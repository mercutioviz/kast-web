# KAST Web

A web-based interface for the Kali Automated Scan Tool (KAST), providing an intuitive way to configure, execute, and manage security scans through your browser.

## Features

- **Easy Scan Configuration**: Web form interface for setting up scans
- **Plugin Selection**: Choose which security tools to run
- **Scan History**: Track all your scans with filtering and search capabilities
- **Report Viewing**: View and download HTML reports directly in the browser
- **Scan Management**: Re-run or delete scans with ease
- **RESTful API**: Programmatic access to scan data

## Technology Stack

### Backend
- Flask (Python web framework)
- SQLAlchemy (Database ORM)
- SQLite (Database)
- WTForms (Form handling)

### Frontend
- Bootstrap 5 (UI framework)
- Bootstrap Icons
- Jinja2 (Templating)

## Installation

### Prerequisites

- Python 3.8 or higher
- KAST CLI tool installed with launcher script at `/usr/local/bin/kast`
- pip (Python package manager)

### Setup

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

4. **Configure environment variables (optional):**
   ```bash
   cp .env.example .env
   # Edit .env with your preferred settings
   ```

5. **Initialize the database:**
   The database will be automatically created when you first run the application.

## Running the Application

### Development Server

```bash
python3 run.py
```

The application will be available at `http://localhost:5000`

### Production Deployment

For production, use a WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

For a complete production setup with Nginx:

1. Install Gunicorn and create a systemd service
2. Configure Nginx as a reverse proxy
3. Set up SSL/TLS certificates
4. Configure environment variables for production

## Configuration

Configuration is managed through `config.py` and environment variables:

- **SECRET_KEY**: Flask secret key (set via environment variable in production)
- **DATABASE_URL**: Database connection string (default: SQLite in `~/kast-web/db/`)
- **KAST_CLI_PATH**: Path to KAST CLI launcher script (default: `/usr/local/bin/kast`)
- **KAST_RESULTS_DIR**: Directory for scan results (default: `~/kast_results/`)

## Project Structure

```
kast-web/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── models.py                # Database models
│   ├── forms.py                 # WTForms
│   ├── utils.py                 # Helper functions
│   ├── routes/
│   │   ├── main.py              # Main routes
│   │   ├── scans.py             # Scan management
│   │   └── api.py               # API endpoints
│   ├── templates/               # Jinja2 templates
│   └── static/                  # CSS, JS, images
├── config.py                    # Configuration
├── requirements.txt             # Python dependencies
├── run.py                       # Development server
└── README.md                    # This file
```

## API Endpoints

KAST Web provides a RESTful API:

- `GET /api/scans` - List all scans (with pagination)
- `GET /api/scans/{id}` - Get scan details
- `GET /api/plugins` - List available plugins
- `GET /api/stats` - Get scan statistics

### Example API Usage

```bash
# Get all scans
curl http://localhost:5000/api/scans

# Get specific scan
curl http://localhost:5000/api/scans/1

# Get available plugins
curl http://localhost:5000/api/plugins

# Get statistics
curl http://localhost:5000/api/stats
```

## Usage

1. **Navigate to the home page** at `http://localhost:5000`
2. **Configure a new scan:**
   - Enter target domain
   - Select scan mode (passive/active)
   - Choose plugins (or leave empty for all)
   - Configure advanced options if needed
3. **Submit the scan** - it will execute and redirect to the scan details page
4. **View scan history** to see all past scans
5. **View reports** for completed scans

## Database

The SQLite database is stored at `~/kast-web/db/kast.db` by default.

### Database Schema

**Scans Table:**
- Stores scan configuration and metadata
- Tracks scan status (pending, running, completed, failed)
- Links to scan results

**ScanResults Table:**
- Stores individual plugin results
- Links to parent scan
- Tracks findings count and output paths

## Future Enhancements

Planned features for future releases:

- User authentication and multi-user support
- Asynchronous scan execution with Celery
- Real-time progress updates via WebSockets
- Scan scheduling and automation
- Scan comparison tools
- Email notifications
- Advanced analytics and dashboards

## Troubleshooting

### Common Issues

**Issue: Plugins not showing up**
- Ensure KAST CLI launcher script exists at `/usr/local/bin/kast`
- Check that KAST CLI path is correct in `config.py`
- Verify KAST CLI works: `kast --list-plugins`
- Ensure KAST's virtual environment is properly set up

**Issue: Scans failing**
- Check KAST CLI is executable
- Verify target domain is valid
- Check scan logs in the output directory
- Ensure required security tools are installed

**Issue: Database errors**
- Ensure `~/kast-web/db/` directory exists and is writable
- Delete database file to reset: `rm ~/kast-web/db/kast.db`
- Restart the application to recreate database

**Issue: Permission errors**
- Ensure proper file permissions on project directory
- Check that output directory (`~/kast_results/`) is writable

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

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write/update tests
5. Submit a pull request

## License

This project is part of the KAST ecosystem.

## Support

For issues, questions, or contributions, please refer to the main KAST project documentation.

## Acknowledgments

- Built with Flask and Bootstrap
- Integrates with KAST CLI tool
- Inspired by the need for user-friendly security scanning interfaces
