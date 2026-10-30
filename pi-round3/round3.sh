#!/usr/bin/env bash
# Round 3 of the pi customization work (details and the adoption rules: the roadmap document, section "round3").
# 11 batches in 3 stages, no input needed. Roughly 10-20 hours in all: the hard tasks are the unknown
# (a hard run takes a guess of 5-10 minutes: at 5 minutes the whole round is about 11 hours, at 10 minutes about 20).
#   stage 1  about 1 h      dev tasks   think-low-c  v1-b  abl-agents  abl-ext
#   stage 2  about 6-12 h   hard tasks  hard-low  hard-v1  hard-blank  hard-low-b
#   stage 3  about 4-8 h    hard tasks  hard-agents  hard-ext      and  hard-fid (task p17 only, 6 repetitions)
# Run it from the arena folder (the folder that contains arena.py):
#       cd ~/pi/arena && bash ../round3.sh
# Look at the plan without running anything:   bash ../round3.sh --plan
# If it stops for any reason (closed terminal, Ctrl-C, reboot), run the same command again: finished runs are kept
# and skipped. One results file per stage is written when the stage ends (send it to me as soon as it appears, there is
# no need to wait for the whole round), and the last lines say which files there are.
# A dead gateway stops the script after 3 runs in a row got no answer from the model (instead of wasting the hours);
# fix it, run the same command again, and the runs that got no answer are redone.
# Before a long run: switch the PC's sleep mode to "never" (a sleeping PC makes the run in progress time out).
set -u

PLAN=0
case "${1:-}" in
  "" ) ;;
  --plan ) PLAN=1 ;;
  * ) echo "usage: bash round3.sh [--plan]"; exit 2 ;;
esac

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f arena.py ] || { echo "arena.py not found here. cd into your arena folder first (cd ~/pi/arena)."; exit 1; }
for d in v1 variants/v1-agents variants/v1-ext variants/v1-fid; do
  [ -d "$HERE/$d" ] || { echo "$HERE/$d not found (extract the whole tgz next to the arena folder)."; exit 1; }
done
[ -f configs/setup.json ] || { echo "configs/setup.json not found: this arena folder has never run 'python3 arena.py day1'."; exit 1; }

# Knobs for testing this script itself against a mock gateway. Leave them unset for the real run.
REPS="${ROUND3_REPS:-3}"
DEV_TASKS="${ROUND3_DEV_TASKS:-dev}"
HARD_TASKS="${ROUND3_HARD_TASKS:-hard}"
FID_TASKS="${ROUND3_FID_TASKS:-p17}"
FID_REPS="${ROUND3_FID_REPS:-6}"
HARD_TIMEOUT="${ROUND3_HARD_TIMEOUT:-1200}"
INFRA_PAUSE="${ROUND3_INFRA_PAUSE:-60}"

STAGE1="think-low-c v1-b abl-agents abl-ext"
STAGE2="hard-low hard-v1 hard-blank hard-low-b"
STAGE3="hard-agents hard-ext hard-fid"
PACKED=()
CURRENT=""
FINISHED=0
T0=$(date +%s)

stamp() { date '+%F %T'; }
elapsed() { local s=$(( $(date +%s) - T0 )); printf '%dh%02dm' $((s / 3600)) $(( (s % 3600) / 60 )); }

# infra_rows <label>: how many runs of the batch have, as their newest attempt, one that got no answer from the model
# (gateway down, quota used up, the agent failing to start; the arena flags such runs I)
infra_rows() {
  python3 - "$1" <<'PY'
import glob, json, os, sys
best = {}
for p in glob.glob(os.path.join("runs", sys.argv[1], "*", "result.json")):
    try:
        r = json.load(open(p, encoding="utf-8"))
    except Exception:
        continue
    k = (r.get("agent"), r.get("task"), r.get("rep"))
    if k not in best or r.get("attempt", 1) > best[k].get("attempt", 1):
        best[k] = r
print(sum(1 for r in best.values() if r.get("infra_error")))
PY
}

# batch <label> <tasks> <timeout> <reps> [more suite options...]
# Gateway trouble is handled here, because a long unattended run must neither stop for one hiccup nor spend the
# remaining hours on a dead gateway: the arena stops the batch when 3 runs in a row get no answer from the model
# (exit code 4); runs that did get no answer are redone once the batch is complete (up to 2 more passes, 60 s apart),
# or at the next start of this script.
batch() {
  local label="$1" tasks="$2" timeout="$3" reps="$4"; shift 4
  echo
  echo "################ $(stamp)  (elapsed $(elapsed))  batch $label: tasks $tasks, $reps repetitions, timeout ${timeout}s"
  if [ "$PLAN" = 1 ]; then echo "  python3 arena.py suite --label $label --agents pi --tasks $tasks --reps $reps --timeout $timeout --skip tasks --no-pack --stop-after-infra 3 --redo-infra $*"; return 0; fi
  local pass=1 rc n redo
  while true; do
    redo=()
    n="$(infra_rows "$label")"
    if [ "${n:-0}" -gt 0 ]; then
      redo=(--redo run,report)
      echo "  $n run(s) of $label got no answer from the model earlier (gateway trouble): redoing them now"
    fi
    python3 arena.py suite --label "$label" --agents pi --tasks "$tasks" --reps "$reps" --timeout "$timeout" --skip tasks --no-pack \
        --stop-after-infra 3 --redo-infra ${redo[@]+"${redo[@]}"} "$@"
    rc=$?
    if [ $rc -ne 0 ]; then
      echo
      if grep -q 'failed (exit 4)' "suite/$label/state.json" 2>/dev/null; then
        echo "!! batch $label stopped: 3 runs in a row got no answer from the model. Is the gateway running and answering?"
        echo "   Check it, then run the same command again: the runs that got no answer are redone, nothing else is lost."
      else
        echo "!! batch $label stopped (exit code $rc). Run the same command again to continue."
      fi
      return $rc
    fi
    n="$(infra_rows "$label")"
    [ "${n:-0}" -eq 0 ] && return 0
    if [ $pass -ge 3 ]; then
      echo "  note: $n run(s) of $label still got no answer from the model after 3 passes; they stay flagged I in the results and are left out of the comparison."
      return 0
    fi
    pass=$((pass + 1))
    echo "  $n run(s) of $label got no answer from the model. Pausing ${INFRA_PAUSE}s, then redoing them (pass $pass of 3)."
    sleep "$INFRA_PAUSE"
  done
}

# pack_stage <title> <labels...>: one results file for the labels that have runs
pack_stage() {
  local title="$1"; shift
  local args=() l
  for l in "$@"; do [ -d "runs/$l" ] && args+=(--label "$l"); done
  [ ${#args[@]} -gt 0 ] || return 0
  echo
  echo "== packing the results of $title =="
  python3 arena.py pack "${args[@]}" || { echo "!! packing failed"; return 1; }
  local f; f="$(ls -t arena-results-*.txt 2>/dev/null | head -1)"
  [ -n "$f" ] && PACKED+=("$title: $f")
  return 0
}

on_exit() {
  if [ "$PLAN" = 1 ] || [ "$FINISHED" = 1 ]; then return; fi
  echo
  echo "Stopped before the end (elapsed $(elapsed)). Run the same command again to continue; nothing is lost."
  if [ -n "$CURRENT" ]; then pack_stage "the unfinished stage (so far)" $CURRENT; fi
  if [ ${#PACKED[@]} -gt 0 ]; then
    echo; echo "Results files written in this session (plain text, no keys inside):"
    printf '  %s\n' "${PACKED[@]}"
  fi
}
trap on_exit EXIT
trap 'exit 130' INT TERM

echo "round 3: $(stamp)   plan: stage 1 (dev tasks, 4 batches), stage 2 (hard tasks, 4 batches), stage 3 (hard tasks, 3 batches)"

if [ "$PLAN" != 1 ]; then
  echo
  if [ -f .round3-taskcheck-ok ]; then
    echo "== step 0: the task check passed earlier (delete the file .round3-taskcheck-ok to redo it) =="
  else
    echo "== step 0: do all the tasks work on this machine? (about 3-5 minutes, no tokens) =="
    python3 arena.py tasks --check --tasks all > /tmp/round3-taskcheck.log 2>&1
    if [ $? -ne 0 ]; then
      cat /tmp/round3-taskcheck.log
      echo; echo "!! the task check failed: nothing was run. Copy the output above to me."
      FINISHED=1
      exit 1
    fi
    echo "tasks OK: $(grep -c '^check .*: OK' /tmp/round3-taskcheck.log) of $(grep -c '^check ' /tmp/round3-taskcheck.log)"
    if grep -q '^check .*SKIPPED' /tmp/round3-taskcheck.log; then
      echo "note: some tasks are skipped because a program they need is not installed; they will be left out of the batches:"
      grep '^check .*SKIPPED' /tmp/round3-taskcheck.log
    fi
    touch .round3-taskcheck-ok
  fi
fi

# ---- stage 1: dev tasks, thinking low. The third baseline batch and a second v1 batch measure the noise;
#      abl-agents (AGENTS.md only) and abl-ext (everything except AGENTS.md) say which half of v1 changes behaviour.
CURRENT="$STAGE1"
batch think-low-c "$DEV_TASKS" 900 "$REPS" --pi-thinking low || exit $?
batch v1-b        "$DEV_TASKS" 900 "$REPS" --pi-thinking low --pi-config "$HERE/v1" || exit $?
batch abl-agents  "$DEV_TASKS" 900 "$REPS" --pi-thinking low --pi-config "$HERE/variants/v1-agents" || exit $?
batch abl-ext     "$DEV_TASKS" 900 "$REPS" --pi-thinking low --pi-config "$HERE/variants/v1-ext" || exit $?
[ "$PLAN" = 1 ] || pack_stage "stage 1 (dev tasks, ablation)" $STAGE1
CURRENT=""

# ---- stage 2: hard tasks. low against pi's own default (high), the v1 pack, and a repeat of low for the noise.
CURRENT="$STAGE2"
batch hard-low   "$HARD_TASKS" "$HARD_TIMEOUT" "$REPS" --pi-thinking low || exit $?
batch hard-v1    "$HARD_TASKS" "$HARD_TIMEOUT" "$REPS" --pi-thinking low --pi-config "$HERE/v1" || exit $?
batch hard-blank "$HARD_TASKS" "$HARD_TIMEOUT" "$REPS" || exit $?
batch hard-low-b "$HARD_TASKS" "$HARD_TIMEOUT" "$REPS" --pi-thinking low || exit $?
[ "$PLAN" = 1 ] || pack_stage "stage 2 (hard tasks)" $STAGE2
CURRENT=""

# ---- stage 3: which half of v1 matters on hard tasks, and the file-fidelity gate on the one task built for it.
CURRENT="$STAGE3"
batch hard-agents "$HARD_TASKS" "$HARD_TIMEOUT" "$REPS" --pi-thinking low --pi-config "$HERE/variants/v1-agents" || exit $?
batch hard-ext    "$HARD_TASKS" "$HARD_TIMEOUT" "$REPS" --pi-thinking low --pi-config "$HERE/variants/v1-ext" || exit $?
batch hard-fid    "$FID_TASKS"  "$HARD_TIMEOUT" "$FID_REPS" --pi-thinking low --pi-config "$HERE/variants/v1-fid" || exit $?
[ "$PLAN" = 1 ] || pack_stage "stage 3 (hard tasks, ablation, fidelity gate)" $STAGE3
CURRENT=""

FINISHED=1
echo
echo "=================================================================================================="
if [ "$PLAN" = 1 ]; then
  echo "That was the plan only; nothing was run."
else
  echo "Round 3 finished at $(stamp) (elapsed $(elapsed))."
  echo "Send me these results files (plain text, no keys inside):"
  printf '  %s\n' "${PACKED[@]}"
fi
