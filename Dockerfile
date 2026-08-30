# Icarus brain container. The brain is almost pure
# Python stdlib; the ONE dependency is fastembed (requirements.txt) for local,
# free, offline semantic-retrieval embeddings — the embedder runs server-side in
# this container, so retrieval never depends on the end user's hardware. We also
# add git + gh because the brain shells out to them to ingest a public repo when
# a user switches repos in the app (see evals/ingest.py). Embeddings stay local.
FROM python:3.12-slim

# git (clone the code subtree) + gh (fetch PRs/issues via the GitHub API).
# gh authenticates public-repository bulk GraphQL calls from the GH_TOKEN env
# var set on the host. Production must use a dedicated, least-privilege machine
# credential here, never a founder's broad personal token. Private ingestion
# overrides it per subprocess with the caller's request-scoped token.
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

# Run as non-root; /app must remain writable for caches and per-user corpora.
RUN useradd -m -u 1000 user
WORKDIR /app
RUN chown user:user /app
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# The one Python dependency: fastembed (local embeddings). ONNX Runtime +
# tokenizers, no PyTorch, so the image stays small. As a non-root user with no
# virtualenv, pip installs into /home/user/.local (added to PATH above).
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=user . .

# Bake the embedding model and default corpus cache so runtime boots warm.
ENV FASTEMBED_CACHE_PATH=/app/.fastembed_cache
RUN python -m demo.warm_cache

# Azure injects $PORT. Production also requires the GitHub bearer gate.
ENV HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "-m", "demo.server"]
