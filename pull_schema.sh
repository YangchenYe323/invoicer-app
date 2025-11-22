#!/bin/bash

# Source the .env file
if [ -f .env ]; then
    source .env
fi

# We need pg_dump binary
echo "Checking for $PG_DUMP binary..."
if ! command -v $PG_DUMP &> /dev/null; then
    echo "$PG_DUMP could not be found. Please install it."
    exit 1
fi
echo "$PG_DUMP found."

# We need to get the database name from the .env file
if [ -z "$DATABASE_URL" ]; then
    echo "DATABASE_URL is not set"
    exit 1
fi

# We need to get the database name from the DATABASE_URL
$PG_DUMP "${DATABASE_URL}" --schema-only > schema.sql