#!/bin/sh
test -n "$SENTINEL_GATEWAY_API_KEY" || {
  echo "SENTINEL_GATEWAY_API_KEY is empty — refusing to start an unauthenticated gateway" >&2
  exit 1
}
