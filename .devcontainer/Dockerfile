FROM localhost/emacs-gui:latest

USER root
RUN apk add --no-cache nodejs npm
# this is not added automatically and without it devcontainer.el fails
LABEL devcontainer.metadata='[{"remoteUser":"tsb","workspaceFolder":"/workspaces"}]'

WORKDIR /workspaces

USER tsb
