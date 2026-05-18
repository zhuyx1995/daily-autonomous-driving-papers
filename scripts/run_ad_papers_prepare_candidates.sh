#!/bin/bash
set -euo pipefail

repo_root="/Users/zhuyuxiao/.openclaw/workspace"
cd "$repo_root"

export TZ=Asia/Shanghai
today="$(/bin/date +%F)"
ym="$(/bin/date +%Y-%m)"
tmp_dir="tmp/${ym}/${today}"
report_path="reports/${ym}/${today}.md"
mkdir -p "$tmp_dir"

q1="autonomous driving end-to-end planning perception"
q2="autonomous driving world model BEV prediction"
q3="autonomous driving imitation learning trajectory safety"

scripts/run_ad_papers_search.sh "$q1" "$tmp_dir/search_q1.xml"
/bin/sleep 3.5
scripts/run_ad_papers_search.sh "$q2" "$tmp_dir/search_q2.xml"
/bin/sleep 3.5
scripts/run_ad_papers_search.sh "$q3" "$tmp_dir/search_q3.xml"

scripts/run_ad_papers_extract_ids.sh "$tmp_dir/search_q1.xml" "$tmp_dir/search_q1_ids.txt"
scripts/run_ad_papers_extract_ids.sh "$tmp_dir/search_q2.xml" "$tmp_dir/search_q2_ids.txt"
scripts/run_ad_papers_extract_ids.sh "$tmp_dir/search_q3.xml" "$tmp_dir/search_q3_ids.txt"

cat "$tmp_dir/search_q1_ids.txt" "$tmp_dir/search_q2_ids.txt" "$tmp_dir/search_q3_ids.txt" | /usr/bin/sort -u > "$tmp_dir/candidate_ids_all.txt"

scripts/run_ad_papers_history_ids.sh reports 30 "$tmp_dir/history_ids_30d.tsv"
/usr/bin/awk -F '\t' '{print $2}' "$tmp_dir/history_ids_30d.tsv" | /usr/bin/sort -u > "$tmp_dir/history_ids_30d.txt"

if [ -f "$report_path" ]; then
  scripts/run_ad_papers_existing_ids.sh "$report_path" "$tmp_dir/today_existing_ids.txt"
else
  : > "$tmp_dir/today_existing_ids.txt"
fi

cat "$tmp_dir/history_ids_30d.txt" "$tmp_dir/today_existing_ids.txt" | /usr/bin/sort -u > "$tmp_dir/excluded_ids.txt"
/usr/bin/comm -23 "$tmp_dir/candidate_ids_all.txt" "$tmp_dir/excluded_ids.txt" > "$tmp_dir/todo_ids.txt"

printf 'TODAY=%s\n' "$today"
printf 'YM=%s\n' "$ym"
printf 'REPORT=%s\n' "$report_path"
printf 'TMP_DIR=%s\n' "$tmp_dir"
printf 'CANDIDATE_ALL=%s\n' "$tmp_dir/candidate_ids_all.txt"
printf 'EXCLUDED=%s\n' "$tmp_dir/excluded_ids.txt"
printf 'TODO=%s\n' "$tmp_dir/todo_ids.txt"
printf 'TODO_COUNT=%s\n' "$(/usr/bin/wc -l < "$tmp_dir/todo_ids.txt" | /usr/bin/tr -d ' ')"
