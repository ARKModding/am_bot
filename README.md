# am_bot

A feature-rich Discord bot built for the ARK Modding community. Built with [discord.py](https://discordpy.readthedocs.io/) and deployable to Kubernetes via Helm.

## Features

### Member Management
- **Greetings** — Automatically welcomes new members in the system channel
- **Quarantine** — Spam protection with honeypot channels and cross-channel duplicate detection
- **Role Assignment** — Reaction-based role self-assignment with automatic reaction reset

### Community Features
- **Starboard** — Messages with 5+ ⭐ reactions get featured in a starboard channel
- **Server Stats** — Live member, boost, modder, and mapper counts displayed in channel names
- **Workshop** — Voice channel-linked text channel with automatic access management and cleanup

### Communication
- **Responses** — Configurable command responses defined in JSON
- **Invite Response** — Staff can respond to invite help requests via email (AWS SES)

## Requirements

- Python 3.10 or higher
- Discord Bot Token
- AWS credentials (for email functionality via SES)

## Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/ARKModding/am_bot.git
cd am_bot

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
echo "BOT_TOKEN=your_bot_token_here" > .env

# Run the bot
python run.py
```

### Docker

```bash
# Build the image
docker build -t am_bot .

# Create .env file with your configuration
cp .env_SAMPLE .env
# Edit .env with your values

# Run the container
docker run -d --rm --name am_bot --env-file .env am_bot
```

### Kubernetes (Helm)

```bash
# Install via Helm
helm upgrade --install am-bot ./helm/am-bot -f values.yaml
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `BOT_TOKEN` | Discord bot authentication token | Yes |
| `AWS_ACCESS_KEY_ID` | AWS access key for SES | For email |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for SES | For email |
| `QUARANTINE_HONEYPOT_CHANNEL_ID` | Channel ID for honeypot quarantine | No |
| `QUARANTINE_ROLE_ID` | Role ID to assign to quarantined users | No |
| `SPAM_SIMILARITY_THRESHOLD` | Similarity ratio for spam detection (0.0-1.0, default: 0.85) | No |
| `SPAM_CHANNEL_THRESHOLD` | Number of channels for spam trigger (default: 3) | No |
| `MESSAGE_HISTORY_SECONDS` | Message history retention in seconds (default: 3600) | No |
| `SPAM_MIN_MESSAGE_LENGTH` | Minimum message length for spam detection (default: 20) | No |

### Configuration Files

- `am_bot/cogs/command_responses.json` — Custom command trigger/response mappings
- `am_bot/cogs/assignable_roles.json` — Reaction role configuration
- `am_bot/constants.py` — Server-specific channel and role IDs

## Development

### Setup

```bash
# Install development dependencies
pip install -e '.[dev]'

# Install pre-commit hooks
pre-commit install
```

### Testing

```bash
# Run all tests with tox
tox

# Run only unit tests
tox -e unittest

# Run only linting
tox -e lint

# Run tests directly with pytest
pytest tests/ -v

# Run with coverage
coverage run -m pytest tests/
coverage report
```

### Code Quality

The project uses the following tools:
- **black** — Code formatting (line length: 79)
- **isort** — Import sorting
- **ruff** — Fast linting
- **bandit** — Security analysis

All checks are run via pre-commit hooks and in CI.

## Project Structure

```
am_bot/
├── am_bot/
│   ├── __init__.py          # Package init, version
│   ├── bot.py                # Main ARKBot class
│   ├── constants.py          # Server-specific IDs
│   ├── ses.py                # AWS SES email utility
│   └── cogs/
│       ├── greetings.py      # Welcome messages, hello command
│       ├── invite_response.py # Email responses to invite requests
│       ├── quarantine.py     # Spam detection and honeypot
│       ├── responses.py      # Custom command responses
│       ├── role_assignment.py # Reaction-based role assignment
│       ├── server_stats.py   # Live stat channel updates
│       ├── starboard.py      # Star reaction feature board
│       ├── workshop.py       # Workshop voice/text channel management
│       ├── command_responses.json
│       └── assignable_roles.json
├── tests/                    # Test suite (90%+ coverage required)
├── helm/am-bot/              # Kubernetes Helm chart
├── pyproject.toml            # Project configuration
├── requirements.txt          # Runtime dependencies
├── tox.ini                   # Test automation
├── Dockerfile                # Container build
└── run.py                    # Application entrypoint
```

## Contributing

1. Fork the repository
2. Clone your fork
3. Create a virtual environment and install dev dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -e '.[dev]'
   ```
4. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```
5. Create a feature branch
6. Make your changes
7. Test with your own bot token in a test server
8. Ensure tests pass and coverage remains ≥90%:
   ```bash
   tox
   ```
9. Create a pull request

## License

This project is maintained by the ARK Modding community.
