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

unset ZEPHYR_BASE
west completion bash > $HOME/west-completion.bash
echo 'source $HOME/west-completion.bash' >> $HOME/.bashrc

history -c
