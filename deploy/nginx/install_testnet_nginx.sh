#!/usr/bin/env bash
# Install nginx site for public testnet (TLS via certbot — operator runs separately).
set -euo pipefail

DOMAIN="${1:-testnet.example.com}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TEMPLATE="$ROOT/deploy/nginx/testnet.example.conf"
SITE_NAME="${NGINX_SITE_NAME:-abs-testnet}"
AVAILABLE="/etc/nginx/sites-available/$SITE_NAME"
ENABLED="/etc/nginx/sites-enabled/$SITE_NAME"

if [[ ! -f "$TEMPLATE" ]]; then
  echo "FAIL: missing $TEMPLATE" >&2
  exit 1
fi

if ! command -v nginx >/dev/null 2>&1; then
  echo "Install nginx first: sudo apt install nginx certbot python3-certbot-nginx" >&2
  exit 1
fi

tmp="$(mktemp)"
sed "s/testnet.example.com/$DOMAIN/g" "$TEMPLATE" > "$tmp"
sudo cp "$tmp" "$AVAILABLE"
rm -f "$tmp"
sudo ln -sf "$AVAILABLE" "$ENABLED"

echo "OK: installed $AVAILABLE (server_name=$DOMAIN)"
echo "  Certbot webroot: sudo mkdir -p /var/www/certbot"
echo "  Test config:  sudo nginx -t"
echo "  Reload:       sudo systemctl reload nginx"
echo "  TLS:          sudo certbot --nginx -d $DOMAIN"
echo "  Upstream:     seed HTTP :19080 RPC :19085 (see .env.testnet)"
