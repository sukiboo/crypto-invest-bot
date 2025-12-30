#!/usr/bin/env bash
set -euo pipefail

ENV_LOCAL_PATH="./.env"

if [[ ! -f "$ENV_LOCAL_PATH" ]]; then
  echo "ERROR: $ENV_LOCAL_PATH not found."
  exit 1
fi

# Load environment variables from .env
set -a
source "$ENV_LOCAL_PATH"
set +a

echo "==> 📦 Pull latest code on server"
ssh "${SERVER_USER}@${SERVER_HOST}" << EOF >/dev/null 2>&1
set -euo pipefail
APPDIR="\$HOME/${SERVER_PATH}"

# Clone or update repo
if [[ ! -d "\$APPDIR/.git" ]]; then
  git clone "${REPO_URL}" "\$APPDIR"
else
  # Only do git operations if repo already exists
  git -C "\$APPDIR" fetch --prune --tags
  # checkout default branch (origin/HEAD) and pull
  DEFAULT_BRANCH=\$(git -C "\$APPDIR" rev-parse --abbrev-ref origin/HEAD | sed "s|origin/||")
  git -C "\$APPDIR" checkout -q "\$DEFAULT_BRANCH"
  git -C "\$APPDIR" pull --ff-only
fi
EOF

echo "==> 🔑 Copy \`.env\` to server"
scp "$ENV_LOCAL_PATH" "${SERVER_USER}@${SERVER_HOST}:~/${SERVER_PATH}/.env" >/dev/null 2>&1
ssh "${SERVER_USER}@${SERVER_HOST}" "chmod 600 ~/${SERVER_PATH}/.env" >/dev/null 2>&1

echo "==> 🚀 Build and run the container"
ssh "${SERVER_USER}@${SERVER_HOST}" << EOF >/dev/null 2>&1
set -euo pipefail
APPDIR="\$HOME/${SERVER_PATH}"

# Create logs directory with write permissions for container user
mkdir -p "\$APPDIR/logs"
chmod 777 "\$APPDIR/logs"

# Build fresh image
docker rm -f "${IMAGE_NAME}" >/dev/null 2>&1 || true
cd "\$APPDIR"
docker build -t "${IMAGE_NAME}:latest" .

# Run continuously with auto-restart
docker run -d --name "${IMAGE_NAME}" \\
  --restart unless-stopped \\
  --env-file "\$APPDIR/.env" \\
  -v "\$APPDIR/logs:/app/logs" \\
  "${IMAGE_NAME}:latest"
EOF

echo "==> ✅ Success"
