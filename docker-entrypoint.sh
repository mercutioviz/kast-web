#!/bin/sh
set -e

# POSIX sh only. The base image's /bin/sh is dash, which has no array slicing:
# an earlier version used "${@:2}" and every container exited immediately with
# "Bad substitution". Use shift + "$@" instead.

case "$1" in
    serve)
        shift
        exec kast-web serve --host 0.0.0.0 "$@"
        ;;
    worker)
        shift
        exec kast-web worker "$@"
        ;;
    dev)
        shift
        exec kast-web dev --host 0.0.0.0 "$@"
        ;;
    *)
        exec "$@"
        ;;
esac
