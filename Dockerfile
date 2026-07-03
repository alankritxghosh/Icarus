# Icarus brain — container for cloud hosting (Render). The brain itself is pure
# Python stdlib (no pip installs); we only add git + gh because the brain shells
# out to them to ingest a public repo when a user switches repos in the app
# (see evals/ingest.py). Public repos only, on free hosted models.
FROM python:3.12-slim

# git (clone the code subtree) + gh (fetch PRs/issues via the GitHub API).
# gh authenticates non-interactively from the GH_TOKEN env var set on the host.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates curl \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

# Render (and most PaaS) inject $PORT and expect the process to bind 0.0.0.0.
# The Host guard is opened via ICARUS_ALLOWED_HOSTS=* and the GitHub bearer gate
# (ICARUS_REQUIRE_GITHUB_AUTH=1) becomes the real boundary — both set in render.yaml.
ENV HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "-m", "demo.server"]
