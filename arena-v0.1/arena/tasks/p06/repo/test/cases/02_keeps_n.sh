run_case() {
  for i in 1 2 3 4 5 6; do
    echo "run $i" > "$TMP/app.log"
    "$ROTATE" -n 3 "$TMP"
  done
  assert_content "$TMP/app.log.1" "run 6"
  assert_content "$TMP/app.log.2" "run 5"
  assert_content "$TMP/app.log.3" "run 4"
  assert_missing "$TMP/app.log.4"
}
