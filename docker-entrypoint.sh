#!/bin/sh
set -e

case "$1" in
    serve)
        exec kast-web serve --host 0.0.0.0 "${@:2}"
        ;;
    worker)
        exec kast-web worker "${@:2}"
        ;;
    dev)
        exec kast-web dev --host 0.0.0.0 "${@:2}"
        ;;
    *)
        exec "$@"
        ;;
esac
