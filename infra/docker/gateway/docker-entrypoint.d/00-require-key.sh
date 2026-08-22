#!/bin/sh
set -eu

case "${SENTINEL_GATEWAY_MODE:-probe}" in
  probe)
    test -n "${SENTINEL_GATEWAY_API_KEY:-}" || {
      echo "SENTINEL_GATEWAY_API_KEY is empty — refusing to start an unauthenticated probe gateway" >&2
      exit 1
    }
    ;;
  dast)
    test -n "${SENTINEL_DAST_API_KEY:-}" || {
      echo "SENTINEL_DAST_API_KEY is empty — refusing to start an unauthenticated DAST gateway" >&2
      exit 1
    }
    ;;
  *)
    echo "Unknown SENTINEL_GATEWAY_MODE — expected probe or dast" >&2
    exit 1
    ;;
esac
