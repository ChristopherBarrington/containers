#! /usr/bin/env bash
# Print the image name and tag for an image directory. The directory name is the tag:
#   images/SAMtools/1.21     ->  ghcr.io/<owner>/containers/samtools:1.21
#   images/SAMtools/1.21--1  ->  ghcr.io/<owner>/containers/samtools:1.21--1
# The tool directory keeps the authors' capitalisation (images/BWA), but image names must be
# lower case, so the tool is lowercased in the image name: images/BWA/0.7.18 -> .../bwa:0.7.18
# With --version, print only the tool's version, the part of the tag before `--`.

set -o errexit -o nounset -o pipefail

mode=image
if [[ ${1:-} == --version ]]; then
	mode=version
	shift
fi

dir=${1%/}
# Image names must be lower case
registry=$(echo "${REGISTRY:-ghcr.io/christopherbarrington/containers}" | tr '[:upper:]' '[:lower:]')

if [[ ! -f ${dir}/Dockerfile ]]; then
	echo "[ERROR] no Dockerfile in ${dir}" >&2
	exit 1
fi

tag=$(basename "${dir}")
tool=$(basename "$(dirname "${dir}")" | tr '[:upper:]' '[:lower:]')
version=${tag%--*}

if [[ ${tag} == *--* && ! ${tag##*--} =~ ^[1-9][0-9]*$ ]]; then
	echo "[ERROR] ${dir}: the rebuild number after '--' must be a whole number from 1, found '${tag##*--}'" >&2
	exit 1
fi

case ${mode} in
	image)   echo "${registry}/${tool}:${tag}" ;;
	version) echo "${version}" ;;
esac
