run_case() {
  echo data > "$TMP/app.log"
  out="$("$ROTATE" -d "$TMP")"
  assert_eq "would rotate $TMP/app.log" "$out" "dry run output"
  assert_missing "$TMP/app.log.1"
  assert_content "$TMP/app.log" "data"
}
