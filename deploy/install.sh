#!/usr/bin/env bash
# One-time hosting setup for LOT Store on this server. Run from the project root:
#   bash deploy/install.sh
set -euo pipefail

HOSTNAME_FQDN="store.layersoftruth.org"
NGINX_PORT=8167
APP_PORT=8067
TUNNEL_SERVICE="cloudflared-kaduna-cng"
TUNNEL_CFG="/etc/cloudflared/config.yml"
cd "$(dirname "$0")/.."

echo "==> Installing systemd service and nginx site"
sudo install -m 644 deploy/lot-store.service /etc/systemd/system/lot-store.service
sudo install -m 644 deploy/nginx-lot-store.conf /etc/nginx/conf.d/lot-store.conf
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable --now lot-store
sudo systemctl reload nginx

echo "==> Waiting for the app on :$APP_PORT"
for _ in $(seq 1 20); do
    curl -fsS -o /dev/null "http://127.0.0.1:$APP_PORT/" -H "Host: $HOSTNAME_FQDN" -H "X-Forwarded-Proto: https" && break
    sleep 1
done
curl -sS -o /dev/null -w "   app via nginx: HTTP %{http_code}\n" "http://127.0.0.1:$NGINX_PORT/" -H "Host: $HOSTNAME_FQDN"

echo "==> Adding $HOSTNAME_FQDN to the Cloudflare Tunnel"
if grep -q "hostname: $HOSTNAME_FQDN\$" "$TUNNEL_CFG"; then
    echo "   already present, skipping"
else
    sudo cp -p "$TUNNEL_CFG" "$TUNNEL_CFG.bak-$(date +%Y%m%d%H%M%S)"
    sudo sed -i "s|^  - service: http_status:404|  - hostname: $HOSTNAME_FQDN\n    service: http://localhost:$NGINX_PORT\n  - service: http_status:404|" "$TUNNEL_CFG"
    cloudflared tunnel --config "$TUNNEL_CFG" ingress validate
    cloudflared tunnel --config "$TUNNEL_CFG" ingress rule "https://$HOSTNAME_FQDN"
    # Brief (~5s) reconnect for every site on this tunnel.
    sudo systemctl restart "$TUNNEL_SERVICE"
fi

echo
echo "Done. Remaining manual step: point DNS for $HOSTNAME_FQDN at the tunnel"
echo "  Cloudflare dashboard > layersoftruth.org > DNS: CNAME 'store' ->"
echo "  a6314630-89ca-4efb-9b99-e5ed3823fafa.cfargotunnel.com (Proxied), replacing the old record."
