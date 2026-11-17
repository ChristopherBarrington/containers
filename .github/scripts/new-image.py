#! /usr/bin/env python3
"""Create an image directory from an 'Add an image' issue, and update the READMEs.

  new-image.py --issue <event.json>   create images/<Tool>/<tag>/ from the issue in a GitHub event
  new-image.py --update-docs          only regenerate the README tables from the image directories

An issue either lists conda packages, which are installed by the template Dockerfile, or names a base
image to extend with Dockerfile instructions. The base image is pinned by digest, looked up with
`docker buildx imagetools inspect` (or given with --base-digest).

For an existing version a rebuild directory (<version>--<n>) is created. Validation commands are
optional; without them no validate-image.sh is written. For a new tool, the issue must also give a
description, a documentation URL and a citation, which are used to write the tool README. Errors are
printed to stderr as one line each, for the workflow to post on the issue.
"""

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
IMAGES = ROOT / 'images'
TEMPLATES = ROOT / '.github' / 'templates'
REGISTRY = os.environ.get('REGISTRY', 'ghcr.io/christopherbarrington/containers').lower()

NAME_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._+-]*$')
PACKAGE_PATTERN = re.compile(r'^[A-Za-z0-9_.:=<>!*,+-]+$')
BASE_IMAGE_PATTERN = re.compile(r'^[a-z0-9][a-z0-9._/-]*(:[A-Za-z0-9_][A-Za-z0-9_.-]*)?(@sha256:[0-9a-f]{64})?$')
DIGEST_PATTERN = re.compile(r'^sha256:[0-9a-f]{64}$')
NO_RESPONSE = '_No response_'


class RequestError(Exception):
	pass


def parse_issue_body(body):
	"""Split an issue-form body into {heading: value}; '### Heading' lines start each field."""
	fields = {}
	heading = None
	lines = []
	for line in (body or '').replace('\r\n', '\n').split('\n'):
		if line.startswith('### '):
			if heading is not None:
				fields[heading] = '\n'.join(lines)
			heading = line[4:].strip()
			lines = []
		elif heading is not None:
			lines.append(line)
	if heading is not None:
		fields[heading] = '\n'.join(lines)
	cleaned = {}
	for key, value in fields.items():
		value = value.strip()
		# a field may be wrapped in a code fence when written by hand
		fence = re.match(r'^```[^\n]*\n(.*)\n```$', value, re.DOTALL)
		if fence:
			value = fence.group(1).strip()
		cleaned[key.lower()] = '' if value == NO_RESPONSE else value
	return cleaned


def natural_key(text):
	return [int(part) if part.isdigit() else part.lower() for part in re.split(r'(\d+)', text)]


def split_tag(tag):
	"""'1.21--2' -> ('1.21', 2); '1.21' -> ('1.21', 0)."""
	if '--' in tag:
		version, rebuild = tag.rsplit('--', 1)
		return version, int(rebuild)
	return tag, 0


def tag_directories(tool_dir):
	return [d for d in tool_dir.iterdir() if d.is_dir() and (d / 'Dockerfile').is_file()]


def versions_and_tags(tool_dir):
	"""[(version, [tags in rebuild order])], newest version first."""
	versions = {}
	for d in tag_directories(tool_dir):
		version, rebuild = split_tag(d.name)
		versions.setdefault(version, []).append((rebuild, d.name))
	ordered = sorted(versions, key=natural_key, reverse=True)
	return [(v, [tag for _, tag in sorted(versions[v])]) for v in ordered]


def markdown_table(header, rows):
	widths = [max(len(str(cell)) for cell in column) for column in zip(header, *rows)]
	lines = [
		'| ' + ' | '.join(cell.ljust(width) for cell, width in zip(header, widths)) + ' |',
		'| ' + ' | '.join(':' + '-' * (width - 1) for width in widths) + ' |',
	]
	lines += ['| ' + ' | '.join(cell.ljust(width) for cell, width in zip(row, widths)) + ' |' for row in rows]
	return '\n'.join(lines)


def replace_table(text, first_header_cell, table):
	pattern = re.compile(r'^\| ' + re.escape(first_header_cell) + r' .*\n(?:\|.*\n?)*', re.MULTILINE)
	if not pattern.search(text):
		raise RequestError(f'no table starting with "{first_header_cell}" to update')
	return pattern.sub(table + '\n', text, count=1)


def update_tool_readme(tool_dir):
	readme = tool_dir / 'README.md'
	text = readme.read_text()
	rows = [(version, ', '.join(f'[`{tag}`]({tag}/)' for tag in tags)) for version, tags in versions_and_tags(tool_dir)]
	text = replace_table(text, 'Version', markdown_table(('Version', 'Tags'), rows))
	# point the pull and exec examples at the newest tag
	image = tool_dir.name.lower()
	latest = versions_and_tags(tool_dir)[0][1][-1]
	text = re.sub(re.escape(f'{REGISTRY}/{image}:') + r'\S+', f'{REGISTRY}/{image}:{latest}', text)
	text = re.sub(r'\b' + re.escape(image) + r'_\S+?\.sif\b', f'{image}_{latest}.sif', text)
	readme.write_text(text)


def update_main_readme():
	readme = ROOT / 'README.md'
	text = readme.read_text()
	tools = sorted((d for d in IMAGES.iterdir() if d.is_dir()), key=lambda d: d.name.lower())
	rows = [(f'[{d.name}](images/{d.name}/)', f'`{REGISTRY}/{d.name.lower()}`') for d in tools]
	if not rows:
		rows = [('None yet', '')]
	readme.write_text(replace_table(text, 'Tool', markdown_table(('Tool', 'Package'), rows)))


def update_docs():
	for tool_dir in IMAGES.iterdir():
		if tool_dir.is_dir() and (tool_dir / 'README.md').is_file():
			update_tool_readme(tool_dir)
	update_main_readme()


def find_tool_dir(tool):
	"""Use an existing tool directory whatever the capitalisation, so one tool never gets two."""
	for d in IMAGES.iterdir():
		if d.is_dir() and d.name.lower() == tool.lower():
			return d, True
	return IMAGES / tool, False


def next_tag(tool_dir, version):
	if not (tool_dir / version).exists():
		return version
	rebuilds = [split_tag(d.name)[1] for d in tag_directories(tool_dir) if split_tag(d.name)[0] == version]
	return f'{version}--{max(rebuilds) + 1}'


def package_lines(text):
	packages = []
	for line in text.splitlines():
		line = line.strip()
		if line.startswith('- '):
			line = line[2:].strip()
		if not line or line.startswith('#'):
			continue
		if not PACKAGE_PATTERN.match(line):
			raise RequestError(f'"{line}" is not a conda package specification, for example bioconda::samtools=1.21')
		packages.append(line)
	return packages


def check_tool_version(tool_names, version, packages):
	"""A package named after the tool must be pinned to the requested version, so the tag matches what is installed."""
	for spec in packages:
		match = re.match(r'^(?:[A-Za-z0-9_.-]+::)?([A-Za-z0-9_.-]+)(.*)$', spec)
		name, constraint = match.group(1), match.group(2)
		if name.lower() not in tool_names:
			continue
		pinned = re.fullmatch(r'==?([^=,|<>!*]+)(?:=[^=]+)?', constraint)
		if not pinned:
			raise RequestError(f'"{spec}" must pin {name} to the version being added, for example {name}={version}')
		if pinned.group(1) != version:
			raise RequestError(f'the Version field is {version}, but "{spec}" installs {name} {pinned.group(1)}; make them match')


def resolve_base_image(base, digest=None):
	"""Return 'name[:tag]@sha256:...' so the base image cannot change under a published tag."""
	if not BASE_IMAGE_PATTERN.match(base):
		raise RequestError(f'"{base}" is not an image reference, for example bioconductor/bioconductor_docker:3.23-r-4.6.1')
	if '@' in base:
		return base
	if digest is None:
		try:
			result = subprocess.run(
				['docker', 'buildx', 'imagetools', 'inspect', base, '--format', '{{json .Manifest}}'],
				capture_output=True, text=True, check=True, timeout=120)
			digest = json.loads(result.stdout)['digest']
		except (OSError, subprocess.SubprocessError, ValueError, KeyError):
			raise RequestError(f'could not find the image {base}; check its name and tag')
	if not DIGEST_PATTERN.match(digest):
		raise RequestError(f'"{digest}" is not an image digest')
	return f'{base}@{digest}'


def extended_dockerfile(base, instructions):
	for line in instructions.splitlines():
		if re.match(r'^\s*FROM\b', line, re.IGNORECASE):
			raise RequestError('the Dockerfile instructions must not contain FROM; the base image is set from the Base image field')
	lines = [f'FROM {base}', '']
	if instructions.strip():
		lines += [instructions.strip(), '']
	return '\n'.join(lines)


def environment_yaml(tool, packages):
	lines = [f'name: {tool.lower()}', 'channels:', '  - conda-forge', '  - bioconda', '  - nodefaults', 'dependencies:']
	lines += [f'  - {p}' for p in packages]
	return '\n'.join(lines) + '\n'


def validate_script(commands):
	return '#! /usr/bin/env bash\nset -o errexit\n' + commands.strip() + '\n'


def example_command(tool, commands):
	"""The first validation command up to any pipe, for the README's exec example; the tool's name without one."""
	lines = [line for line in commands.splitlines() if line.strip() and not line.strip().startswith('#')]
	if not lines:
		return tool.lower()
	return lines[0].split('|', 1)[0].replace('2>&1', '').strip()


def bioconda_link(packages):
	for p in packages:
		match = re.match(r'^bioconda::([A-Za-z0-9._-]+)', p)
		if match:
			return f'https://bioconda.github.io/recipes/{match.group(1)}/README.html'
	return None


def tool_readme(tool, tag, fields, packages, commands):
	image = tool.lower()
	links = [f'- [Documentation]({fields["documentation url"]})']
	if fields.get('source repository url'):
		links.append(f'- [Source repository]({fields["source repository url"]})')
	bioconda = bioconda_link(packages)
	if bioconda:
		links.append(f'- [Bioconda package]({bioconda})')
	return '\n'.join([
		f'# {tool}',
		'',
		fields['description'],
		'',
		'## Pulling an image',
		'',
		'```bash',
		f'apptainer pull docker://{REGISTRY}/{image}:{tag}',
		'```',
		'',
		'```bash',
		f'apptainer exec {image}_{tag}.sif {example_command(tool, commands)}',
		'```',
		'',
		'| Version | Tags |',
		'| :------ | :--- |',
		'',
		'## Links',
		'',
		*links,
		'',
		'## Citation',
		'',
		fields['citation'],
		'',
	])


def create_from_issue(event_path, base_digest=None):
	event = json.loads(pathlib.Path(event_path).read_text())
	fields = parse_issue_body(event['issue'].get('body'))

	tool = fields.get('tool', '')
	version = fields.get('version', '')
	commands = fields.get('validation commands', '')
	if not NAME_PATTERN.match(tool):
		raise RequestError(f'"{tool}" is not a valid tool name: use letters, digits, ".", "_", "+" or "-"')
	if not NAME_PATTERN.match(version) or '--' in version:
		raise RequestError(f'"{version}" is not a valid version: use letters, digits, ".", "_", "+" or "-", without "--"')
	base = fields.get('base image', '')
	packages = package_lines(fields.get('conda packages', ''))
	if base and packages:
		raise RequestError('give either a base image or conda packages, not both')
	if not base and not packages:
		raise RequestError('no conda packages or base image were given')

	tool_dir, exists = find_tool_dir(tool)
	if base:
		base = resolve_base_image(base, base_digest)
		dockerfile = extended_dockerfile(base, fields.get('dockerfile instructions', ''))
	else:
		check_tool_version({tool.lower(), tool_dir.name.lower()}, version, packages)
	if not exists:
		missing = [f for f in ('description', 'documentation url', 'citation') if not fields.get(f)]
		if missing:
			raise RequestError(f'{tool} is a new tool, so these fields are needed: ' + ', '.join(missing))

	tag = next_tag(tool_dir, version)
	tag_dir = tool_dir / tag
	tag_dir.mkdir(parents=True)
	if base:
		(tag_dir / 'Dockerfile').write_text(dockerfile)
	else:
		(tag_dir / 'Dockerfile').write_text((TEMPLATES / 'Dockerfile').read_text())
		(tag_dir / 'environment.yaml').write_text(environment_yaml(tool_dir.name, packages))
	if commands.strip():
		(tag_dir / 'validate-image.sh').write_text(validate_script(commands))
	if not exists:
		(tool_dir / 'README.md').write_text(tool_readme(tool_dir.name, tag, fields, packages, commands))
	update_docs()

	outputs = {
		'tool': tool_dir.name,
		'tag': tag,
		'dir': str(tag_dir.relative_to(ROOT)),
		'image': f'{REGISTRY}/{tool_dir.name.lower()}:{tag}',
		'new_tool': str(not exists).lower(),
		'validated': str(bool(commands.strip())).lower(),
		'base': base,
	}
	for key, value in outputs.items():
		print(f'[INFO] {key}: {value}')
	if 'GITHUB_OUTPUT' in os.environ:
		with open(os.environ['GITHUB_OUTPUT'], 'a') as handle:
			for key, value in outputs.items():
				handle.write(f'{key}={value}\n')


def main():
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	group = parser.add_mutually_exclusive_group(required=True)
	group.add_argument('--issue', metavar='EVENT_JSON', help='GitHub event file for an issue')
	group.add_argument('--update-docs', action='store_true', help='only regenerate the README tables')
	parser.add_argument('--base-digest', metavar='DIGEST', help='digest of the base image, instead of looking it up')
	args = parser.parse_args()
	try:
		if args.issue:
			create_from_issue(args.issue, args.base_digest)
		else:
			update_docs()
	except RequestError as error:
		print(f'[ERROR] {error}', file=sys.stderr)
		sys.exit(1)


if __name__ == '__main__':
	main()
