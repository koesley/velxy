#!/bin/sh
cd "$(dirname "$0")/velxy-main" || exit 1
if command -v python3 >/dev/null 2>&1; then
  exec python3 launch_velxtria.py
fi
echo 'Python 3 is required. Install it and run this launcher again.'
exit 1
