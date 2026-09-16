#!/usr/bin/env sh
set -eu
DESTDIR=${DESTDIR:-}
PREFIX=${PREFIX:-/usr}
PURGE=${1:-}
if [ "$PREFIX" != /usr ]; then printf '%s\n' 'Only PREFIX=/usr is supported.' >&2; exit 1; fi
case "$DESTDIR" in ""|/*) ;; *) printf '%s\n' 'DESTDIR must be empty or absolute.' >&2; exit 1;; esac
if [ "$PURGE" != "" ] && [ "$PURGE" != "--purge-data" ]; then
  printf '%s\n' 'Usage: uninstall-linux.sh [--purge-data]' >&2; exit 1
fi
rm -f "$DESTDIR$PREFIX/lib/systemd/system/stageforge.service" \
      "$DESTDIR$PREFIX/lib/systemd/system/stageforge-witness.service" \
      "$DESTDIR$PREFIX/lib/udev/rules.d/70-stageforge-uwb.rules" \
      "$DESTDIR$PREFIX/lib/sysusers.d/stageforge.conf" \
      "$DESTDIR$PREFIX/lib/tmpfiles.d/stageforge.conf"
rm -rf "$DESTDIR$PREFIX/libexec/stageforge" "$DESTDIR$PREFIX/share/stageforge"
if [ "$PURGE" = "--purge-data" ]; then
  rm -rf "$DESTDIR/var/lib/stageforge"
  printf '%s\n' 'Removed StageForge files and state data. The service account was not deleted.'
else
  printf '%s\n' "Removed StageForge program files; preserved $DESTDIR/var/lib/stageforge. The service account was not deleted."
fi
