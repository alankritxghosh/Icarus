# Icarus brain — container for cloud hosting (Render). The brain is almost pure
# Python stdlib; the ONE dependency is fastembed (requirements.txt) for local,
# free, offline semantic-retrieval embeddings — the embedder runs server-side in
# this container, so retrieval never depends on the end user's hardware. We also
# add git + gh because the brain shells out to them to ingest a public repo when
# a user switches repos in the app (see evals/ingest.py). Public repos on free
# hosted writers; embeddings are always local (no key, no quota, no egress).
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

# The one Python dependency: fastembed (local embeddings). ONNX Runtime +
# tokenizers, no PyTorch, so the image stays small.
RUN pip install --no-cache-dir -r requirements.txt

# Boot WARM, not cold. A fresh Render deploy wipes the git-ignored vector cache,
# so without this the container would download the fastembed model AND re-embed
# the whole default corpus on startup -- long enough to leave the service stuck
# "starting up" (docs/HANDOFF.md §4). Baking both into the image at build time
# makes runtime a fast cache hit. FASTEMBED_CACHE_PATH pins the model download to
# a stable in-image path used at BOTH build and runtime (fastembed reads this env
# var); demo.warm_cache embeds the default corpus into evals/corpus/vectors.json,
# exactly the cache the server's cold path would produce.
ENV FASTEMBED_CACHE_PATH=/app/.fastembed_cache
RUN python -m demo.warm_cache

# Render (and most PaaS) inject $PORT and expect the process to bind 0.0.0.0.
# The Host guard is opened via ICARUS_ALLOWED_HOSTS=* and the GitHub bearer gate
# (ICARUS_REQUIRE_GITHUB_AUTH=1) becomes the real boundary — both set in render.yaml.
ENV HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "-m", "demo.server"]
