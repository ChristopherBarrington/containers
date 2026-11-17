# images

One directory per tool, with one directory per published tag inside it:

```
images/<Tool>/
├── README.md        what the tool is, its tags, links and citation
└── <tag>/           for example 1.21, or 1.21--1 for a rebuild
    ├── Dockerfile
    ├── environment.yaml     conda images only
    └── validate-image.sh    optional
```

`images/<Tool>/<tag>/` is published as `ghcr.io/christopherbarrington/containers/<tool>:<tag>`, with the tool name in lower case. Published directories are never changed; a rebuild gets a new `--<n>` directory.

To add an image, open an issue with the **Add an image** or **Extend an existing image** form. See [CONTRIBUTING.md](../.github/CONTRIBUTING.md) for the conventions and worked examples.
