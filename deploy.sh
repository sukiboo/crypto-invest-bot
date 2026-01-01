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

# Add GitHub to known_hosts if using SSH URL
if [[ "${REPO_URL}" == git@* ]]; then
  if ! ssh-keygen -F github.com >/dev/null 2>&1; then
    ssh-keyscan -t rsa github.com >> ~/.ssh/known_hosts 2>/dev/null
  fi
fi

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

# Check if Docker needs to be installed
echo "==> 🚀 Build and run the container"
if ! ssh "${SERVER_USER}@${SERVER_HOST}" "command -v docker &> /dev/null" >/dev/null 2>&1; then
  echo "==> 🐋 Installing docker"
fi

ssh "${SERVER_USER}@${SERVER_HOST}" << EOF >/dev/null 2>&1
set -euo pipefail
APPDIR="\$HOME/${SERVER_PATH}"

# Install Docker if not present
DOCKER_CMD="docker"
if ! command -v docker &> /dev/null; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq ca-certificates curl
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  echo \\
    "deb [arch=\$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \\
    \$(. /etc/os-release && echo "\$VERSION_CODENAME") stable" | \\
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update -qq
  sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "\$USER"
  # Use sudo for docker commands since group change requires new session
  DOCKER_CMD="sudo docker"
fi

# Check if we can run docker (with or without sudo)
if ! \$DOCKER_CMD info &> /dev/null; then
  # Try with sudo if regular docker failed
  if [[ "\$DOCKER_CMD" != "sudo docker" ]]; then
    DOCKER_CMD="sudo docker"
  fi
fi

# Build fresh image
\$DOCKER_CMD rm -f "${IMAGE_NAME}" >/dev/null 2>&1 || true
cd "\$APPDIR"
\$DOCKER_CMD build -t "${IMAGE_NAME}:latest" . >/dev/null 2>&1

# Run continuously with auto-restart
\$DOCKER_CMD run -d --name "${IMAGE_NAME}" \\
  --restart unless-stopped \\
  --env-file "\$APPDIR/.env" \\
  -v "\$APPDIR/logs:/app/logs" \\
  "${IMAGE_NAME}:latest" >/dev/null 2>&1
EOF

echo "==> ✅ Success"
