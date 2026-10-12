#!/bin/bash
# see also, https://github.com/blues/note-zephyr/blob/main/.devcontainer/onCreateCommand.sh

if [ -n "$1" ]; then
    mkdir -p $1
    echo "Workspace folder created at $1"
fi

echo "alias ll='ls -lah'" >> $HOME/.bashrc
cat << 'EOF' >> ~/.bashrc
git_custom_status() {
    branch=$(git symbolic-ref --short HEAD 2>/dev/null)
    if [ -n "$branch" ]; then
        echo "($branch)"
    fi
}
export PS1='$(git_custom_status)\[\033[0;36m\][\W]\[\033[0m\]\$ '
EOF

# Disable git's "dubious ownership" check (safe.directory) inside the container.
#
# On Docker Desktop for macOS the workspace is a VirtioFS bind mount, and file
# ownership is emulated: a freshly created directory can briefly report uid 0
# (root) before settling on the container user's uid. `west update` runs
# `git init` followed immediately by `git remote add` for each project, so it
# regularly hits this window and fails with:
#   fatal: detected dubious ownership in repository at '.../deps/<project>'
# (reproduced in ~2/3 of rapid init+remote-add attempts; see also
# https://github.com/docker/for-mac/issues/6734 and
# https://github.com/docker/for-mac/issues/6243).
#
# Per-path safe.directory entries don't help since git matches them exactly and
# west creates many nested repositories. The container is single-user, so the
# check protects nothing here. Set at system scope because VS Code copies the
# host's ~/.gitconfig into the container.
if ! git config --system --get-all safe.directory | grep -qxF '*'; then
    sudo git config --system --add safe.directory '*'
fi

unset ZEPHYR_BASE
west completion bash > $HOME/west-completion.bash
echo 'source $HOME/west-completion.bash' >> $HOME/.bashrc

history -c
