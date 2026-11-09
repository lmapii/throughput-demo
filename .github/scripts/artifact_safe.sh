#!/bin/sh
# Prints $1 with the characters GitHub doesn't allow in artifact names
# (" : < > | * ? \ / CR LF) replaced by '_'. Used wherever an ECW board name
# becomes part of an artifact name, so uploads and downloads agree.
printf '%s' "$1" | tr '\r\n' '__' | sed 's/[":<>|*?\\/]/_/g'
