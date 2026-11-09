
ARG BASE_IMAGE="mcr.microsoft.com/devcontainers/base:ubuntu"
FROM ${BASE_IMAGE} AS base

ARG TZ
ARG CLAUDE_CODE_VERSION=latest
ARG NODE_VERSION=20
ARG USERNAME=user
ARG ENABLE_FZF_KEYBINDINGS=true
ARG WORKSPACE_FOLDER=/workspace

ENV TZ="$TZ"

USER root

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# basics

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        tree \
    && rm -rf /var/lib/apt/lists/*

# create workspace and config dirs
RUN mkdir -p /workspace /home/$USERNAME/.claude && \
    chown -R $USERNAME:$USERNAME /workspace /home/$USERNAME/.claude

WORKDIR /workspace

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# claude code

USER root
# node.js isn't included in base:ubuntu, needed for Claude Code
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Claude Code as the non-root user
USER $USERNAME
ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=$PATH:/usr/local/share/npm-global/bin

RUN sudo mkdir -p /usr/local/share/npm-global && \
    sudo chown -R $USERNAME:$USERNAME /usr/local/share/npm-global && \
    npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# other

# fuzzy find using fzf
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
        less fzf man-db unzip gnupg2 gh vim \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

USER $USERNAME
RUN if [ "$ENABLE_FZF_KEYBINDINGS" = "true" ]; then \
      echo 'if command -v fzf >/dev/null 2>&1; then' >> /home/$USERNAME/.bashrc && \
      echo '  eval "$(fzf --bash 2>/dev/null)" || { \
        [ -f /usr/share/doc/fzf/examples/key-bindings.bash ] && source /usr/share/doc/fzf/examples/key-bindings.bash; \
        [ -f /usr/share/fzf/key-bindings.bash ] && source /usr/share/fzf/key-bindings.bash; }' >> /home/$USERNAME/.bashrc && \
      echo 'fi' >> /home/$USERNAME/.bashrc ; \
    fi

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# _artifacts in PATH for root, `remoteEnv` in `devcontainer.json` only covers `user`

# `sudo` replaces PATH with `secure_path`
USER root
RUN sed -i "s|secure_path=\"|secure_path=\"${WORKSPACE_FOLDER}/_artifacts:|" /etc/sudoers && \
    visudo -c

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# ensure non-root

USER $USERNAME
