# Contributing

This guide covers how images are defined, named, tagged and published, and how to add one. For pulling and using images, see the [README](../README.md).

## Layout

```
containers/
├── .github/
│   ├── CONTRIBUTING.md             this guide
│   ├── ISSUE_TEMPLATE/
│   │   ├── add-image.yaml          the 'Add an image' issue form, for conda images
│   │   └── extend-image.yaml       the 'Extend an existing image' issue form
│   ├── scripts/
│   │   ├── changed-images.sh       list image directories changed between two commits
│   │   ├── image-tag.sh            print the image name and tag for a directory
│   │   └── new-image.py            create an image directory from an issue; update README tables
│   ├── templates/
│   │   └── Dockerfile              copied into every new conda image directory
│   └── workflows/
│       ├── add-image.yaml          turn an image request issue into a pull request
│       └── build.yaml              build, validate and publish changed images
└── images/
    └── <tool>/
        ├── README.md               what the tool is, available tags, links and citation
        └── <tag>/                  for example 1.21 or 1.21--1
            ├── Dockerfile          how the image is built
            ├── environment.yaml    conda environment installed by the Dockerfile, for conda images
            └── validate-image.sh   optional check run inside the built image
```

Each `images/<tool>/` directory is one GHCR package, and each `<tag>/` directory inside it is exactly one tag in that package.

## Naming

### Tools

- Name the tool directory with the capitalisation used in the tool's original publication, for example `images/BEDTools`, `images/SAMtools` and `images/BWA`, even where the current documentation or repository uses another form. If the tool has no publication, use the capitalisation in its documentation.
- Image names must be lower case, so the package name is always the lower-case form: `images/SAMtools` publishes `ghcr.io/christopherbarrington/containers/samtools`. [`image-tag.sh`](scripts/image-tag.sh) does this conversion.
- Use the same capitalisation in the tool README, its title and prose, and the image's `title` label. Commands keep their real case: `samtools --version`.

### Packages

Packages are published under the repository name, `ghcr.io/<owner>/containers/<tool>`, rather than directly under the owner. If the repository moves to an organisation, every repository there publishes into the same package namespace, and the `containers/` prefix keeps these images apart from others with the same tool names.

## Tags

| Directory                    | Tag                | Meaning                          |
| :--------------------------- | :----------------- | :------------------------------- |
| `images/SAMtools/1.21/`      | `samtools:1.21`    | first build of SAMtools 1.21     |
| `images/SAMtools/1.21--1/`   | `samtools:1.21--1` | first rebuild of SAMtools 1.21   |
| `images/SAMtools/1.21--2/`   | `samtools:1.21--2` | second rebuild of SAMtools 1.21  |

- The directory name is the tag. Before `--` is the tool's own version; after it is the rebuild number, starting from 1. The double hyphen keeps the two apart when a version contains a hyphen, for example `0.7.17-r1188--1`.
- Every tag is fixed: once published, it is never moved or reused, so a project that pins a tag always gets the same image.
- A published directory is never changed. To rebuild (a new base image, a changed environment), add an image for the same version: the next `--<n>` directory is created. The workflow refuses to publish a tag that already exists.
- Because every tag has its own directory, the definition behind any tag can be read directly, or two compared with `diff --recursive images/SAMtools/1.21 images/SAMtools/1.21--1`.
- There is no moving tag such as `latest`.
- A multi-tool image takes the version of its main tool, or its own version if it has no main tool, for example `images/scrnaseq/1.0.0/`.

## Kinds of image

There are two ways to define an image. Both give a tag directory that the build workflow treats the same way: it builds the `Dockerfile`, runs `validate-image.sh` if there is one, and publishes the result. The issue forms write these files for you; this section shows what they write, for adding or checking an image by hand.

### Conda images

Use this for anything available from conda-forge or Bioconda. The image is a conda environment on a small micromamba base image, and every conda image uses the same `Dockerfile`, copied from [`templates/Dockerfile`](templates/Dockerfile). Only `environment.yaml` and `validate-image.sh` differ between images.

For example, a SAMtools 1.21 image in `images/SAMtools/1.21/`:

```
images/SAMtools/1.21/
├── Dockerfile
├── environment.yaml
└── validate-image.sh
```

`Dockerfile`, unchanged from the template. It installs `environment.yaml` into the base environment and puts it on `PATH`, because Apptainer does not run the image's entrypoint for `apptainer exec`:

```dockerfile
FROM mambaorg/micromamba:2.0.5

COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yaml /tmp/environment.yaml
RUN micromamba install --yes --name base --file /tmp/environment.yaml \
	&& micromamba clean --all --yes

# Apptainer does not run the image entrypoint for `exec`, so put the environment on PATH directly
ENV PATH=/opt/conda/bin:$PATH
```

`environment.yaml`, from the form's **Conda packages** field, one line per package:

```yaml
name: samtools
channels:
  - conda-forge
  - bioconda
  - nodefaults
dependencies:
  - bioconda::samtools=1.21
```

`validate-image.sh`, from the form's **Validation commands** field:

```bash
#! /usr/bin/env bash
set -o errexit
samtools --version | grep --quiet "samtools 1.21"
```

An image with several tools lists them all under `dependencies` and checks each one in `validate-image.sh`. The same environment can be created without a container with `conda env create --file environment.yaml`.

### Extended images

Use this to build on another published Docker image, for example to add software to a Bioconductor or Rocker image that conda cannot provide well. There is no `environment.yaml`: the `Dockerfile` is the whole definition.

For example, an R 4.6.1 image in `images/R/4.6.1/`, which adds renv to a Bioconductor image:

```
images/R/4.6.1/
├── Dockerfile
└── validate-image.sh
```

`Dockerfile`. The `FROM` line comes from the form's **Base image** field, pinned to the digest its tag pointed to when the image was added; the rest comes from the **Dockerfile instructions** field:

```dockerfile
FROM bioconductor/bioconductor_docker:3.23-r-4.6.1@sha256:821dbf9ac119eac41f177531c7ca8fc7084c99c04eb218a1aa7f52cb63bad5d9

# install renv from a dated CRAN snapshot, so a rebuild gets the same version
RUN Rscript -e 'install.packages("renv", repos = "https://packagemanager.posit.co/cran/2026-11-16")'
```

`validate-image.sh`, from the form's **Validation commands** field:

```bash
#! /usr/bin/env bash
set -o errexit
Rscript -e 'stopifnot(getRversion() == "4.6.1", BiocManager::version() == "3.23"); library(renv)'
```

An extended image must stay reproducible, because its tag is fixed once published:

- Pin the base image by digest, keeping its tag for readability. Tags such as Bioconductor's are moved when the image is updated, so without the digest a rebuild would change silently. To find the digest by hand: `docker buildx imagetools inspect <image>:<tag>`.
- Pin everything installed on top, for example R packages from a dated CRAN snapshot (`https://packagemanager.posit.co/cran/<YYYY-MM-DD>`) or a named version.
- Name the image after its main software and use that software's version as the version, for example `images/R/4.6.1`. Describe what was added in the tool README.
- Do not rely on the base image's entrypoint: Apptainer does not run it for `apptainer exec`.

A newer base image, or changed additions, is a rebuild: the next `--<n>`, with the new digest.

### Choosing between them

| Situation                                                               | Kind     |
| :---------------------------------------------------------------------- | :------- |
| The software is on conda-forge or Bioconda                              | Conda    |
| Several tools from conda-forge or Bioconda in one image                 | Conda    |
| Adding to an established image, such as Bioconductor or Rocker          | Extended |
| The software needs system packages or an installer conda cannot provide | Extended |

Prefer a conda image where it works: the Dockerfile is shared, the environment can be used without a container, and the version check in the issue form applies.

## Files in a tag directory

### `Dockerfile`

How the image is built. For a conda image it is the template, unchanged; for an extended image it is a pinned `FROM` line and the added instructions. See [Kinds of image](#kinds-of-image).

### `environment.yaml`

Use the channels `conda-forge`, `bioconda` and `nodefaults`, in that order, and pin the main tool to the exact version with its channel:

```yaml
name: samtools
channels:
  - conda-forge
  - bioconda
  - nodefaults
dependencies:
  - bioconda::samtools=1.21
```

> [!NOTE]
> Only the listed packages are pinned, so their dependencies are re-resolved on each build. A lockfile (for example from conda-lock) next to each file would make rebuilds reproducible.

### `validate-image.sh`

A Bash script that the workflow runs inside the built image before it is published. It should fail if the image is not usable. At least:

- run the tool, so a missing library or a tool that is not on `PATH` is caught;
- check that it reports the expected version.

For a multi-tool image, check every tool or package the image is for, for example by importing each Python or R package. The script is optional, but an image without one is published unchecked, and its pull request says so.

```bash
#! /usr/bin/env bash
set -o errexit
samtools --version | grep --quiet "samtools 1.21"
```

## Tool README

Each `images/<tool>/README.md` has these sections:

1. A `# <Tool>` heading in the publication's capitalisation, then a short description of what the tool does.
2. **Pulling an image**: an `apptainer pull` and an `apptainer exec` example using the latest tag, followed by a table of versions and their tags, each tag linking to its directory:

   ```markdown
   | Version | Tags                                   |
   | :------ | :------------------------------------- |
   | 1.21    | [`1.21`](1.21/), [`1.21--1`](1.21--1/) |
   | 1.20    | [`1.20`](1.20/)                        |
   ```

   List versions newest first and each version's tags in rebuild order.
3. **Links**: the documentation, the source repository and the Bioconda package.
4. **Citation**: the publication to cite, with its DOI, plus any later publication the authors ask to be cited.

The `add-image` workflow writes the README for a new tool and keeps the tables in it and in the main [README](../README.md) up to date. Edit the description, links and citation by hand as needed. Changes to README files do not trigger a build.

## Adding an image

Images are added through an issue. The same route adds a new tool, a new version, or a rebuild of an existing version. There are two forms:

- **Add an image**, for a conda image: give the conda packages.
- **Extend an existing image**, for an extended image: give the base image with its tag, and the Dockerfile instructions to add after `FROM`. The workflow looks up the digest the tag points to and pins it.

1. Open an issue with one of the forms, or with `gh` as shown below. Give the tool, the version, the conda packages and, ideally, the validation commands; for a new tool, also the description, documentation URL, source repository URL and citation. If a package is named after the tool, it must be pinned to the same version as the Version field, for example `bioconda::samtools=1.22` for version `1.22`.
2. The `add-image` workflow:
   - creates `images/<Tool>/<tag>/` with a `Dockerfile` (from [the template](templates/Dockerfile) and an `environment.yaml` for a conda image, or the pinned base image and instructions for an extended image) and, if validation commands were given, a `validate-image.sh`. If the version already has an image, the next `--<n>` rebuild is created;
   - writes the tool README for a new tool, and updates the tables in the tool README and the main README;
   - commits this to a branch `add-image/issue-<n>`, opens a pull request and starts a build of the branch, which builds the image and runs its `validate-image.sh` but does not publish it;
   - comments on the issue with a link to the pull request, or with what was wrong with the request.
3. Check the build and the pull request. The build on the pull request waits for approval, because a workflow opened it: approve it in the pull request's checks. To change anything, push to the branch; this runs the build on the pull request again.
4. Merge the pull request. The build workflow publishes the image, and the issue is closed.

No local Docker is needed. The workflow runs when the `add-image` label is added, which the form does when the issue is opened. Only people with triage access or above can add images: for an issue from anyone else, the workflow does nothing until someone with access adds the label.

If a request is wrong, the workflow says so on the issue. Edit the issue, then remove and re-add the `add-image` label to try again. Once an issue has a pull request, adding the label again does nothing; to start again, close the pull request and delete its `add-image/issue-<n>` branch first.

### With `gh`

`gh` cannot fill in an issue form, so write the body that the form would produce: a `### ` heading for each field, followed by its value. The headings must match the form's field names exactly, and the `add-image` label must be added. For a new version or rebuild of an existing tool:

```bash
gh issue create --repo ChristopherBarrington/containers --label add-image --title 'Add an image: SAMtools 1.22' --body-file - <<'BODY'
### Tool

SAMtools

### Version

1.22

### Conda packages

bioconda::samtools=1.22

### Validation commands

samtools --version | grep --quiet "samtools 1.22"
BODY
```

For an extended image, give `### Base image` and `### Dockerfile instructions` in place of `### Conda packages`:

```bash
gh issue create --repo ChristopherBarrington/containers --label add-image --title 'Extend an image: R 4.6.1' --body-file - <<'BODY'
### Tool

R

### Version

4.6.1

### Base image

bioconductor/bioconductor_docker:3.23-r-4.6.1

### Dockerfile instructions

RUN Rscript -e 'install.packages("renv", repos = "https://packagemanager.posit.co/cran/2026-11-16")'

### Validation commands

Rscript -e 'stopifnot(getRversion() == "4.6.1"); library(renv)'
BODY
```

For a new tool, add these fields after the validation commands:

```markdown
### Description

One or two sentences on what the tool does.

### Documentation URL

https://example.org/docs

### Source repository URL

https://github.com/example/tool

### Citation

Author A, Author B. Title. *Journal* 1(2):3–4 (2025). [doi:10.0000/example](https://doi.org/10.0000/example)
```

### Without an issue

The files can also be added by hand on a branch: copy a tag directory, edit it, run `.github/scripts/new-image.py --update-docs` to update the README tables, and open a pull request, which runs the build. An image can also be built from the Actions tab: run the `build` workflow with its directory. It is published only when run on `main`.

## Correcting a published image

A published tag cannot be fixed in place. Publish the corrected image as the next `--<n>` and, if the bad image should not be pulled any more, delete its package version:

```bash
gh api /user/packages/container/containers%2Fsamtools/versions --jq '.[] | [.id, (.metadata.container.tags | join(","))] | @tsv'
```

```bash
gh api --method DELETE /user/packages/container/containers%2Fsamtools/versions/<id>
```

This needs a token with the `delete:packages` scope (`gh auth refresh --scopes delete:packages`).

- Deleting a version removes every tag that points to that image.
- GitHub can restore a deleted version for 30 days.
- Copies already pulled, including `.sif` files, are not affected.
- Do not reuse a deleted tag name unless you are sure nobody pulled it; the workflow would allow it, because the tag no longer exists.

## Publishing

- Images are pushed with the workflow's `GITHUB_TOKEN`, so no secrets are needed.
- Images are published only from `main`: by a push to `main`, or a manual run of the `build` workflow on `main`. Pull requests and manual runs on other branches build and validate only.
- Each image is labelled with the repository (`org.opencontainers.image.source`), the commit it was built from (`revision`), its tool README (`documentation`), and its tool name and version. The `source` label links the package to this repository.
- A new package may be created private. To make it public, open the package on GitHub, then Package settings → Change visibility.
- Do not set up a cleanup policy that deletes old tags; projects depend on them.

## Not supported yet: Apptainer definition files

Every image is built from a `Dockerfile`. Apptainer and Singularity run these images directly, and most `.def` sections have a Dockerfile equivalent: `%post` is `RUN`, `%environment` is `ENV`, `%files` is `COPY`, `%labels` is `LABEL`, and `%runscript` is `CMD` or `ENTRYPOINT`. Convert a definition file rather than adding a second build route.

If definition files are needed later, for example to reuse existing ones or for Apptainer-only features such as `%apprun` apps, the plan is:

- a tag directory holds `apptainer.def` instead of a `Dockerfile`, with the same directory and tag naming;
- the build workflow installs Apptainer, runs `apptainer build`, validates with `apptainer exec image.sif bash validate-image.sh`, and publishes with `apptainer push ... oras://`;
- these images are published under a separate path, such as `ghcr.io/<owner>/containers/sif/<tool>`, because they are pulled with `oras://` rather than `docker://` and Docker cannot use them. Keeping them apart leaves the existing packages and pull commands unchanged;
- pin the base image by digest (`Bootstrap: docker` with `From: name:tag@sha256:...`), as for Dockerfiles;
- check whether GHCR links an `oras://` package to the repository; the OCI labels used for Docker images do not apply to `.sif` files.

## Repository set-up

These settings are needed once, for example after creating or moving the repository:

- Settings → Actions → General → Workflow permissions: **Allow GitHub Actions to create and approve pull requests**, so the `add-image` workflow can open pull requests. The default permissions can stay **Read repository contents and packages permissions**, because each workflow requests the write access it needs.
- An `add-image` label, which the issue form adds and the workflow looks for:

  ```bash
  gh label create add-image --repo ChristopherBarrington/containers --description 'Add a container image' --color 0E8A16
  ```

- The registry path `ghcr.io/christopherbarrington/containers` is the default in [`image-tag.sh`](scripts/image-tag.sh) and [`new-image.py`](scripts/new-image.py); change both if the repository moves.
