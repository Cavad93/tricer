#!/bin/bash
#
# Setup script for Webhook mode
# Run as root: sudo bash deployment/setup-webhook.sh
#

set -e

echo "=================================="
echo "NutriAI Bot - Webhook Setup"
echo "=================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root (sudo bash deployment/setup-webhook.sh)"
    exit 1
fi

# Get domain from user
read -p "Enter your domain (e.g., bot.example.com): " DOMAIN

if [ -z "$DOMAIN" ]; then
    echo "ERROR: Domain cannot be empty"
    exit 1
fi

echo ""
echo "Step 1: Installing required packages..."
apt-get update
apt-get install -y nginx certbot python3-certbot-nginx

echo ""
echo "Step 2: Obtaining SSL certificate from Let's Encrypt..."
certbot certonly --nginx -d "$DOMAIN" --non-interactive --agree-tos --email admin@"$DOMAIN"

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to obtain SSL certificate"
    echo "Make sure:"
    echo "  1. DNS A record for $DOMAIN points to this server's IP"
    echo "  2. Port 80 is accessible from the internet"
    exit 1
fi

echo ""
echo "Step 3: Copying nginx configuration..."
# Copy nginx config
cp deployment/nginx/nutriai-webhook.conf /etc/nginx/sites-available/

# Replace domain in config
sed -i "s/bot\.example\.com/$DOMAIN/g" /etc/nginx/sites-available/nutriai-webhook.conf

# Create symlink
ln -sf /etc/nginx/sites-available/nutriai-webhook.conf /etc/nginx/sites-enabled/

# Remove default config
rm -f /etc/nginx/sites-enabled/default

echo ""
echo "Step 4: Testing nginx configuration..."
nginx -t

if [ $? -ne 0 ]; then
    echo "ERROR: Nginx configuration test failed"
    exit 1
fi

echo ""
echo "Step 5: Reloading nginx..."
systemctl reload nginx

echo ""
echo "Step 6: Generating webhook secret..."
WEBHOOK_SECRET=$(openssl rand -hex 32)

echo ""
echo "Step 7: Updating .env file..."
# Backup .env
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

# Update or add webhook settings
grep -q "USE_WEBHOOK" .env && sed -i "s/^USE_WEBHOOK=.*/USE_WEBHOOK=true/" .env || echo "USE_WEBHOOK=true" >> .env
grep -q "WEBHOOK_URL" .env && sed -i "s|^WEBHOOK_URL=.*|WEBHOOK_URL=https://$DOMAIN/webhook|" .env || echo "WEBHOOK_URL=https://$DOMAIN/webhook" >> .env
grep -q "WEBHOOK_SECRET" .env && sed -i "s/^WEBHOOK_SECRET=.*/WEBHOOK_SECRET=$WEBHOOK_SECRET/" .env || echo "WEBHOOK_SECRET=$WEBHOOK_SECRET" >> .env

echo ""
echo "Step 8: Setting up auto-renewal for SSL certificate..."
# Certbot auto-renewal is set up automatically
systemctl enable certbot.timer
systemctl start certbot.timer

echo ""
echo "=================================="
echo "✅ Webhook mode setup complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "  1. Restart the bot:"
echo "     sudo systemctl restart nutriai-bot"
echo ""
echo "  2. Check bot logs:"
echo "     sudo journalctl -u nutriai-bot -f"
echo ""
echo "  3. Test webhook:"
echo "     curl https://$DOMAIN/health"
echo ""
echo "Configuration:"
echo "  Domain: $DOMAIN"
echo "  Webhook URL: https://$DOMAIN/webhook"
echo "  SSL Certificate: /etc/letsencrypt/live/$DOMAIN/fullchain.pem"
echo ""
echo "Your webhook secret has been saved to .env"
echo "Backup created: .env.backup.*"
echo ""
