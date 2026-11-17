#!/usr/bin/env bash
# A版・B版を、回路図から JLCPCB に送るファイルまで、まとめて作り直す
#   使い方：bash build.sh A B
set -e
cd "$(dirname "$0")"
KP="$HOME/AppData/Local/Programs/KiCad/10.0/bin"
PY="${PY:-$HOME/AppData/Local/Python/bin/python}"
for V in "${@:-A B}"; do
  export VARIANT=$V
  echo "===== $V 版"
  "$KP/python.exe" make_lib.py
  "$KP/python.exe" make_sch.py
  "$KP/python.exe" check_sch.py
  "$KP/python.exe" make_pcb.py
  "$PY" -I route.py
  # 塗りつぶしたあとに、ほかとつながっていない GND があれば、線を足して作り直す（4回まで）
  ok=0
  for k in 1 2 3 4; do
    if "$KP/python.exe" apply_routes.py; then ok=1; break; fi
    "$PY" -I route.py repair
    "$KP/python.exe" make_pcb.py
  done
  if [ $ok = 0 ]; then "$KP/python.exe" apply_routes.py || echo "!!! まだつながっていない GND がある"; fi
  "$KP/python.exe" make_bom.py
  "$PY" -I make_fab.py
done
