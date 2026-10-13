#!/bin/sh
# Re-run the EMS fidelity check for a winter week and a summer week, one container at a time, 1 GB, hard time limit.
# usage (Git Bash on Windows):  MSYS_NO_PATHCONV=1 sh tests/integrity/run_ems.sh C:/path/to/scratch  C:/path/to/repo
# scratch must contain models/lab_optimal_mutated.idf (copy of tests/fixtures/platform/lab_optimal_mutated.idf) and weather.epw
# (copy of backend/user_files/weather.epw, Torino IWEC).
S="$1"; R="$2"
for spec in "jan_week 1 1 1 7" "jul_week 7 1 7 7"; do
  set -- $spec
  docker run --rm --memory=1g -v "$S:/work" -v "$R/tests/integrity:/t:ro" --entrypoint timeout jupyter:smartbuilding-surrogate 1500 \
    python /t/ems_fidelity.py /work/models/lab_optimal_mutated.idf /work/weather.epw /work/ems "$1" "$2" "$3" "$4" "$5" > "$S/ems_$1.log" 2>&1
done
