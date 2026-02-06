# Spotify-Backup

An archival service that performs snapshots of a Spotify library. It captures exhaustive metadata, including ISRC fingerprints and added_at timestamps, ensuring your library can be reconstructed or migrated even if Spotify suddenly ceased to exist or deleted your account—all in one JSON file.

## Metadata Captured

To ensure future-proof backups, the service archives more than just song titles:

- ISRC: The global unique identifier for the specific recording.
- Release Date: To distinguish between original pressings and remasters.
- Added At: Precise timestamp of when the track was saved.
- Album/Artist: Full string metadata for secondary matching.
- Spotify URI: The direct platform-specific link.

## Technical Specifications

The program is designed to run efficiently on low-power hardware, such as a Raspberry Pi, prioritizing minimal storage wear (SD card safe) and memory efficiency.

- Environment: Dockerized Python for consistent dependency management.
- Efficiency: Processes thousands of songs in batches of 50 via the Spotify API to stay within rate limits.
- Notifications: SUCCESS and FAIL runs via Discord webhooks.

## Setup & Usage

### Prerequisites

- A Spotify Developer Account (to obtain Client ID and Secret).
- Docker and Docker Compose installed.
- Discord Webhook URL.

### Configuration

Create a .env file in the root directory with your credentials:

```bash
SPOTIFY_CLIENT_ID=your_id_here
SPOTIFY_CLIENT_SECRET=your_secret_here
DISCORD_WEBHOOK=your_webhook_here
```

### Execution

#### Standard Run

`docker compose run --rm spotify-backup`

#### Test Mode (Skips full download)

`docker compose run -e TEST_MODE=true --rm spotify-backup`

### Updating Logic

If you modify the Python code, rebuild the container:
`docker compose build`

### Automation (Optional)

To truly "set and forget," you can automate the backup using a system cron job. For example, to run the backup on the 1st of every month at 4:00 AM:

1. Open crontab: `crontab -e`

2. Add the following line: `0 4 1 * * cd /path/to/project && /usr/bin/docker compose run --rm spotify-backup >/dev/null 2>&1`

## Disclaimer

This project is a third-party tool and is not affiliated, associated, authorized, endorsed by, or in any way officially connected with Spotify.
