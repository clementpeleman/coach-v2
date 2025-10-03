#!/bin/bash
# Security Setup Script for AI Sports Coach
# This script helps set up the security features

set -e

echo "================================================"
echo "AI Sports Coach - Security Setup"
echo "================================================"
echo ""

# Check if .env exists
if [ -f .env ]; then
    echo "✓ .env file found"
else
    echo "✗ .env file not found"
    echo "  Creating from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✓ Created .env from template"
    else
        echo "✗ .env.example not found!"
        exit 1
    fi
fi

# Generate encryption key if not set
if grep -q "ENCRYPTION_KEY=your_44_character_fernet_key_here" .env; then
    echo ""
    echo "Generating new encryption key..."
    NEW_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')

    # Update .env file with new key
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s|ENCRYPTION_KEY=your_44_character_fernet_key_here|ENCRYPTION_KEY=$NEW_KEY|g" .env
    else
        # Linux
        sed -i "s|ENCRYPTION_KEY=your_44_character_fernet_key_here|ENCRYPTION_KEY=$NEW_KEY|g" .env
    fi
    echo "✓ Generated and saved encryption key"
else
    echo "✓ Encryption key already configured"
fi

# Check Python version
echo ""
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python $PYTHON_VERSION"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip3 install -r requirements.txt > /dev/null 2>&1
echo "✓ Dependencies installed"

# Check if database needs migration
echo ""
echo "================================================"
echo "Setup Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Edit .env file and fill in:"
echo "   - TELEGRAM_BOT_TOKEN"
echo "   - OPENAI_API_KEY"
echo "   - DATABASE_URL"
echo ""
echo "2. If upgrading from old version, run:"
echo "   python scripts/migrate_passwords.py"
echo ""
echo "3. Start the bot:"
echo "   python chat_interface/telegram_bot.py"
echo ""
echo "For more information, see SECURITY.md"
echo ""
