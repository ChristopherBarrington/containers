FROM mambaorg/micromamba:2.0.5

COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yaml /tmp/environment.yaml
RUN micromamba install --yes --name base --file /tmp/environment.yaml \
	&& micromamba clean --all --yes

# Apptainer does not run the image entrypoint for `exec`, so put the environment on PATH directly
ENV PATH=/opt/conda/bin:$PATH
