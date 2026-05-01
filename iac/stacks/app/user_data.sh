#!/bin/bash
set -euo pipefail

# Install Docker and utilities
yum update -y
yum install -y docker aws-cli jq
systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

# ECR login
aws ecr get-login-password --region "${aws_region}" | \
  docker login --username AWS --password-stdin "${ecr_url}"

# Fetch application secrets and write .env
mkdir -p /app
aws secretsmanager get-secret-value \
  --secret-id "${secret_id}" \
  --region "${aws_region}" \
  --query SecretString \
  --output text | \
  jq -r 'to_entries[] | "\(.key)=\(.value)"' > /app/.env

# Pull and start the API container
docker pull "${ecr_url}:${app_image_tag}"

docker run -d \
  --name llmops-api \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file /app/.env \
  "${ecr_url}:${app_image_tag}"

# Systemd unit for reboot persistence
cat > /etc/systemd/system/llmops-api.service << 'EOF'
[Unit]
Description=LLMOps FastAPI service
After=docker.service
Requires=docker.service

[Service]
Restart=always
ExecStartPre=-/usr/bin/docker stop llmops-api
ExecStartPre=-/usr/bin/docker rm llmops-api
ExecStart=/usr/bin/docker start -a llmops-api
ExecStop=/usr/bin/docker stop llmops-api

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable llmops-api
