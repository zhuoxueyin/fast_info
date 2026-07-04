#!/bin/sh
set -eu

if [ "${FASTINFO_BOOTSTRAP:-1}" = "1" ]; then
  python scripts/init_admin_collections.py

  if [ "${FASTINFO_INIT_ADMIN:-1}" = "1" ]; then
    ADMIN_USERNAME="${FASTINFO_ADMIN_USERNAME:-admin}"
    ADMIN_PASSWORD="${FASTINFO_ADMIN_PASSWORD:-admin@2026}"
    python scripts/init_admin.py --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD"
  fi
fi

exec "$@"
