#!/usr/bin/env bash
# install-autofix-button-secret.sh
#
# Provisions AUTOFIX_BUTTON_SECRET in the three places that need it:
#   1. ~/myprojects/news-v2/.env       (local dev — for testing the digest)
#   2. GitHub Actions repo secrets     (CI — quality-digest workflow signs URLs)
#   3. Supabase Edge Function env      (autofix-action verifies signatures)
#
# Run ONCE per project lifetime (or when rotating). Re-running is
# idempotent — the same secret value goes everywhere.
#
# Prereqs:
#   - gh CLI logged in for daijiong1977/news-v2
#   - supabase CLI linked to project ref lfknsvavhiqrsasdfyrs
#
# Usage:  ./install-autofix-button-secret.sh
set -euo pipefail

REPO="$HOME/myprojects/news-v2"
ENV_FILE="$REPO/.env"
GH_REPO="daijiong1977/news-v2"
SUPABASE_REF="lfknsvavhiqrsasdfyrs"
SECRET_NAME="AUTOFIX_BUTTON_SECRET"

# Generate or reuse: if .env already has it, keep that value so the
# three locations stay in sync. Otherwise mint a fresh 256-bit hex.
if grep -q "^${SECRET_NAME}=" "$ENV_FILE" 2>/dev/null; then
    SECRET=$(grep "^${SECRET_NAME}=" "$ENV_FILE" | cut -d= -f2-)
    echo "✓ reusing existing secret from ${ENV_FILE}"
else
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    chmod 600 "$ENV_FILE" 2>/dev/null || true
    printf '%s=%s\n' "$SECRET_NAME" "$SECRET" >> "$ENV_FILE"
    echo "✓ wrote new secret to ${ENV_FILE}"
fi

# 2. GitHub Actions
gh secret set "$SECRET_NAME" -R "$GH_REPO" --body "$SECRET"
echo "✓ set GitHub Actions secret ${SECRET_NAME}"

# 3. Supabase edge function env
supabase secrets set "$SECRET_NAME=$SECRET" --project-ref "$SUPABASE_REF" >/dev/null
echo "✓ set Supabase Edge Function secret ${SECRET_NAME}"

unset SECRET
echo ""
echo "Done. The signature flow now works end-to-end:"
echo "  digest signs URL  →  email recipient clicks  →  edge fn verifies"
