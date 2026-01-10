#!/bin/sh

export ANTHROPIC_API_KEY=$(pass show api/llm/anthropic)
export OPENAI_API_KEY=$(pass show api/llm/openai)

DEVCONTAINER_ARGS="--workspace-folder ."

# Check for --new flag
if [ "$1" = "--new" ]; then
    DEVCONTAINER_ARGS="--remove-existing-container $DEVCONTAINER_ARGS"
    shift
fi

devcontainer up $DEVCONTAINER_ARGS &&
    devcontainer exec --workspace-folder . zsh
