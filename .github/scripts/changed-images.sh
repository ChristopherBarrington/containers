#! /usr/bin/env bash
# Print a JSON array of image directories that changed between two commits.
# With no base commit (or an all-zero one, as on a branch's first push), print every image directory.
# Only files that affect the image count: README changes do not trigger a build.

set -o errexit -o nounset -o pipefail

base=${1:-}
head=${2:-HEAD}

if [[ -z ${base} || ${base} =~ ^0+$ ]]; then
	files=$(git ls-files 'images/*/*/*')
else
	files=$(git diff --name-only --diff-filter=ACMR "${base}" "${head}" -- 'images/*/*/*')
fi

echo "${files}" \
	| { grep --invert-match --extended-regexp '(^|/)README\.md$' || true; } \
	| awk -F/ 'NF >= 4 { print $1 "/" $2 "/" $3 }' \
	| sort -u \
	| while read -r dir; do
		if [[ -f ${dir}/Dockerfile ]]; then
			echo "${dir}"
		fi
	done \
	| jq --raw-input --slurp --compact-output 'split("\n") | map(select(length > 0))'
