#!/bin/bash

# Exit on error
set -e

# Define PATH for cron execution
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# ==========================================
# CONFIGURATION
# ==========================================
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_NAME="Spotify_Backup_$TIMESTAMP.tar.gz"

# Automatically find the project directory regardless of user or path
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Directories
DATA_DIR="$PROJECT_DIR/backups"
SCRIPT_PATH="$PROJECT_DIR/backup_spotify_cloud.sh"
TEMP_WORK_DIR="/tmp/spotify_backup_staging"

# Remote
DEST_REMOTE="gdrive:Server Backups/Spotify-Backups"
LOG_FILE="$PROJECT_DIR/rclone_log.txt"

# Retention
# Linux 'find' command only accepts integers for days, and rclone assume days
LOCAL_RETENTION="30"
# Rclone suffix for Months
CLOUD_RETENTION="6M"

# ==========================================
# FUNCTIONS
# ==========================================

log_msg() {
	echo "$(date): $1" >> "$LOG_FILE"
}

validate_json() {
	# Uses python to verify the JSON is readable
	python3 -m json.tool "$1" > /dev/null 2>&1
	return $?
}

# ==========================================
# EXECUTION
# ==========================================

log_msg "Starting Spotify Cloud Backup..."

# 0. Execute Docker to generate the JSON backups
cd "$PROJECT_DIR"
docker compose run -T --rm spotify-backup

# 1. Create a Clean Staging Area
rm -rf "$TEMP_WORK_DIR"
mkdir -p "$TEMP_WORK_DIR"

# 2. Stage the Script
cp "$SCRIPT_PATH" "$TEMP_WORK_DIR/"

# 3. Stage and Validate Data
shopt -s nullglob
json_files=("$DATA_DIR"/*.json)

if [ ${#json_files[@]} -gt 0 ]; then
	for json_file in "${json_files[@]}"; do
		filename=$(basename "$json_file")
		cp "$json_file" "$TEMP_WORK_DIR/$filename"

		if validate_json "$TEMP_WORK_DIR/$filename"; then
			log_msg "[OK] Verified integrity of $filename"
		else
			log_msg "[CRITICAL] $filename is corrupt! Aborting upload."
			rm -rf "$TEMP_WORK_DIR"
			exit 1
		fi
	done
else
	log_msg "[WARN] No JSON files found in $DATA_DIR. Nothing to compress."
	rm -rf "$TEMP_WORK_DIR"
	exit 0
fi

# 4. Compress the Verified Files
tar -czf "/tmp/$BACKUP_NAME" -C "$TEMP_WORK_DIR" . >> "$LOG_FILE" 2>&1

# 5. Upload to Google Drive
if rclone copy "/tmp/$BACKUP_NAME" "$DEST_REMOTE"; then
	log_msg "[SUCCESS] Uploaded $BACKUP_NAME"

	# 5a. Cloud Retention
	rclone delete "$DEST_REMOTE" --min-age $CLOUD_RETENTION 2>/dev/null || true

	# 5b. Local Storage
	mv "/tmp/$BACKUP_NAME" "$DATA_DIR/$BACKUP_NAME"

	# 5c. Cleanup Raw JSONs
	rm -f "$DATA_DIR"/*.json

	# 5d. Local Retention (Prune old archives)
	find "$DATA_DIR" -iname "Spotify_Backup_*.tar.gz" -mtime +$LOCAL_RETENTION -delete
else
	log_msg "[FAILURE] Upload failed!"
	rm -f "/tmp/$BACKUP_NAME"
fi

# 6. Cleanup Staging
rm -rf "$TEMP_WORK_DIR"