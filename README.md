# containers

Software container images for analysis work. Each image is built by GitHub Actions and published to the GitHub Container Registry (GHCR), where Apptainer, Singularity or Docker can pull it.

## Available tools

| Tool     | Tag(s) | Summary |
| :------- | :----- | :------ |
| None yet |        |         |

Each tool's README describes the tool, lists its tags and gives links and a citation.

## Pulling an image

The examples here use a SAMtools 1.21 image; use the tool and tag you need, from the table above or the tool's README.

With Apptainer or Singularity:

```bash
apptainer pull docker://ghcr.io/christopherbarrington/containers/samtools:1.21
```

```bash
apptainer exec samtools_1.21.sif samtools --version
```

With Docker:

```bash
docker pull ghcr.io/christopherbarrington/containers/samtools:1.21
```

Package names are always lower case, even where the tool's own name is not: SAMtools is pulled as `containers/samtools`.

## Choosing a tag

| Tag                | Meaning                         |
| :----------------- | :------------------------------ |
| `samtools:1.21`    | first build of SAMtools 1.21    |
| `samtools:1.21--1` | first rebuild of SAMtools 1.21  |
| `samtools:1.21--2` | second rebuild of SAMtools 1.21 |

- Before `--` is the tool's version; after it is the rebuild number. A rebuild has the same tool version with a changed environment or base image.
- Tags never change: a published tag always gives the same image, so pin an exact tag in your project.
- There is no `latest` tag.
- The definition behind each tag is in `images/<Tool>/<tag>/`. To see what a rebuild changed, compare its directory with the previous one.

## Using the environment without a container

Images built from a conda environment have an `environment.yaml` in their tag directory, so the same environment can be created with conda:

```bash
conda env create --file images/SAMtools/1.21/environment.yaml
```

Images that extend another image have no `environment.yaml` and can only be used as containers.

## Finding where an image came from

Each image records the commit it was built from and a link to its tool README:

```bash
docker inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' ghcr.io/christopherbarrington/containers/samtools:1.21--1
```

```bash
apptainer inspect samtools_1.21--1.sif
```

## Contributing

To add a tool, version or rebuild, see [CONTRIBUTING.md](.github/CONTRIBUTING.md). It also documents the naming and tagging conventions.
