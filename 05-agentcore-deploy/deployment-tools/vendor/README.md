# vendor/

The Runtime image needs the shared `workshop` package, and `booking_agent.py`
imports `workshop.hybrid_retrieval` directly. That package lives outside this
build context, in `workshop/` at the repository root, so it cannot be reached by
a relative path from inside the image.

`5.1_agentcore_deploy.ipynb` builds it into a wheel here immediately before
launch:

```bash
uv build --wheel --out-dir vendor ../../workshop
```

`agent_requirements.txt` then installs that exact file, and the `Dockerfile`
copies this directory before running the install. The wheel is a build
artifact, so `.gitignore` keeps it out of the repository while keeping the
directory itself tracked. A `COPY vendor/ vendor/` against a directory that
does not exist fails the image build, which is why the directory is committed
and the wheel is not.

The pinned filename in `agent_requirements.txt` carries the package version. If
`workshop/pyproject.toml` ever changes `version`, the wheel-build cell in `5.1`
fails with the new filename and the line to update.
