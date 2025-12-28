# AGENTS.md

Guidelines for AI coding assistants working on the am_bot codebase.

## Project Overview

am_bot is a Discord bot for the ARK Modding community, built with discord.py 2.x. It uses a cog-based architecture where each feature is isolated in its own module under `am_bot/cogs/`.

## Architecture

### Core Components

- **`am_bot/bot.py`** — Main `ARKBot` class extending `discord.ext.commands.Bot`. Handles initialization, intents, and cog loading.
- **`am_bot/cogs/`** — Feature modules (cogs) that encapsulate related functionality.
- **`am_bot/constants.py`** — Server-specific IDs (guild, channels, roles). These are hardcoded for the ARK Modding Discord.
- **`am_bot/ses.py`** — AWS SES email utility used by `invite_response.py`.

### Cog Pattern

Each cog follows this pattern:

```python
import discord
from discord.ext import commands

class MyCog(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot = bot

    def cog_load(self) -> None:
        # Called when cog is loaded — start background tasks here
        self.bot.loop.create_task(self.my_task())

    def cog_unload(self) -> None:
        # Cleanup when cog is unloaded
        pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Event listeners
        pass

    @commands.command()
    async def mycommand(self, ctx):
        """Command docstring shows in help"""
        pass
```

### Adding New Cogs

1. Create the cog file in `am_bot/cogs/`
2. Import and register in `am_bot/bot.py`:
   ```python
   from .cogs.my_cog import MyCog
   # ... in add_cogs():
   await self.add_cog(MyCog(self))
   ```
3. Add corresponding test file in `tests/test_my_cog.py`

## Code Style

### Formatting

- **Line length**: 79 characters
- **Formatter**: black
- **Import sorting**: isort (black profile)
- **Linter**: ruff

Run `tox -e lint` to verify or use pre-commit hooks.

### Conventions

- Use `discord.ext.commands.Bot` type hints for bot parameters
- Prefer `AsyncMock` for async method mocks in tests
- Use `MagicMock` for synchronous Discord objects
- Log using `logging.getLogger(__name__)`
- Background tasks should use `self.bot.loop.create_task()` in `cog_load()`

## Testing

### Test Structure

Tests are in `tests/` with one file per cog:
- `test_bot.py` — Core bot tests
- `test_greetings.py` — GreetingsCog tests
- `test_quarantine.py` — QuarantineCog tests
- etc.

### Test Fixtures

`tests/conftest.py` provides mock factories for Discord objects:

```python
# Available fixture factories:
make_mock_bot()
make_mock_guild()
make_mock_channel()
make_mock_member()
make_mock_message()
make_mock_embed()
make_mock_role()
make_mock_reaction_payload()
make_mock_voice_state()

# Available pytest fixtures:
@pytest.fixture def mock_bot()
@pytest.fixture def mock_guild()
@pytest.fixture def mock_channel()
@pytest.fixture def mock_member()
@pytest.fixture def mock_message()
```

### Writing Tests

```python
import pytest
from am_bot.cogs.my_cog import MyCog
from conftest import make_mock_bot, make_mock_message

@pytest.mark.asyncio
async def test_my_feature():
    bot = make_mock_bot()
    cog = MyCog(bot)
    message = make_mock_message(content="test")
    
    await cog.on_message(message)
    
    message.channel.send.assert_called_once()
```

### Coverage Requirements

- Minimum 90% coverage enforced via `tox -e unittest`
- All new code should have corresponding tests
- Use `coverage run -m pytest tests/ && coverage report` to check

## Running Tests

```bash
# Full test suite (lint + tests on Python 3.10-3.13)
tox

# Just unit tests
tox -e unittest

# Just linting
tox -e lint

# Quick pytest run
pytest tests/ -v

# With coverage
coverage run -m pytest tests/ && coverage report
```

## Dependencies

### Runtime (requirements.txt)
- `discord.py==2.3.2` — Discord API wrapper
- `boto3==1.33.7` — AWS SDK (for SES email)
- `audioop-lts==0.2.1` — Audio support for voice features

### Development (pyproject.toml [dev])
- `pytest`, `pytest-asyncio`, `pytest-cov` — Testing
- `black`, `isort`, `ruff`, `bandit` — Code quality
- `pre-commit` — Git hooks
- `tox` — Test automation

## Common Tasks

### Add a new command response

Edit `am_bot/cogs/command_responses.json`:

```json
{
  "!": {
    "mycommand": {
      "content": "Response text here"
    }
  }
}
```

### Add a new reaction role

Edit `am_bot/cogs/assignable_roles.json`:

```json
{
  "🎮": {
    "name": "Gamer",
    "role_id": 123456789,
    "channel_id": 987654321,
    "message_id": 111222333
  }
}
```

### Add environment-based configuration

1. Read in the cog with `os.getenv()`:
   ```python
   MY_SETTING = int(os.getenv("MY_SETTING", 0))
   ```
2. Document in README.md environment variables table
3. Add to Helm values if needed

## Deployment

### Docker

```bash
docker build -t am_bot .
docker run -d --env-file .env am_bot
```

### Kubernetes/Helm

The Helm chart is in `helm/am-bot/`. Override values in your deployment:

```yaml
# values.yaml
image:
  repository: your-registry/am_bot
  tag: latest
env:
  BOT_TOKEN: "your-token"
```

## Gotchas

1. **Bot intents**: The bot requires `members` and `message_content` intents. Enable in Discord Developer Portal.

2. **Constants are hardcoded**: `constants.py` has ARK Modding-specific IDs. For a different server, these must be changed.

3. **Async in cogs**: All Discord event handlers and commands are async. Use `await` properly and `AsyncMock` in tests.

4. **Reaction role reset**: `RoleAssignmentCog` clears and re-adds reactions every 10 minutes. This is intentional.

5. **Workshop cleanup**: `WorkshopCog` purges messages older than 24 hours from the workshop text channel.

6. **Starboard tracking**: `StarboardCog` loads existing starred message IDs on startup to prevent duplicates.

## Questions?

Check the existing cogs for patterns. The codebase is well-tested — reference `tests/conftest.py` for mock utilities.

