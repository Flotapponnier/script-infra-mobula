# Better Stack Monitor Management

Manage Better Stack monitors via config file. Export all monitors to JSON, edit the config, then sync changes back (dry-run + apply).

## Setup

Create a `.env` file with your API token:
```bash
echo 'BETTERSTACK_API_TOKEN=your-token-here' > .env
```

## Usage

```bash
./manage_monitors.sh
```

**Option 1:** Export all monitors to `monitors_config.json`
**Option 2:** Update monitors from config (shows diff, asks confirmation, then applies)
