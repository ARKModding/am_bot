# am_bot
ARK Modding Discord Bot

## Setup
1. Install Python 3.11 or higher
2. Install requirements.txt

    `pip install -r requirements.txt`
3. Create a .env file in the root directory

    `echo "BOT_TOKEN=<your bot token>" > .env`
4. Run the bot

    `python run.py`

### Docker
1. Install Docker
2. Build the image

    `docker build -t am_bot .`
3. Setup `.env` file (copy `.env_SAMPLE` to `.env` and fill in the values)
4. Run the image

    `docker run -d --rm --name am_bot --env-file .env am_bot`


## Contributing
1. Fork the repository
2. Clone your fork
3. Create a virtual environment

    `python -m venv venv`
4. Install development requirements

    `pip install -e '.[dev]'`
5. Install pre-commit hooks

    `pre-commit install`
6. Create a new branch
7. Make your changes
8. Test your changes with your own Bot Token (see Discord Bot Setup Docs) in your own server
9. Create a pull request
10. Wait for it to be reviewed and merged
