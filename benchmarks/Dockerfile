FROM python:3.14-slim
RUN apt-get update && apt-get install -y --no-install-recommends git g++ \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml /tmp/project/pyproject.toml
# Install dependencies, not a source snapshot: bench-container mounts the
# checkout under test at /work. Preserve SymPy's VCS metadata for the pin check.
RUN python -c 'import tomllib, subprocess; p = tomllib.load(open("/tmp/project/pyproject.toml", "rb")); subprocess.check_call(["python", "-m", "pip", "install", "asv==0.6.6", *p["project"]["optional-dependencies"]["sympy"], *p["project"]["optional-dependencies"]["dev"]])'
RUN python -m pip install "setuptools>=68"
# ASV hardcodes ~/.asv-machine.json; redirect just that file to writable tmpfs.
RUN ln -s /tmp/asv-machine.json /root/.asv-machine.json
