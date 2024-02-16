FROM ubuntu:22.04

RUN apt update \
    && DEBIAN_FRONTEND=noninteractive apt install vim git wget curl python3-pip python3-venv -y \
  	&& apt-get clean \
  	&& rm -rf /var/lib/apt/lists/*

# Ensure that VSCode uses bash as the default shell
SHELL ["/bin/bash", "--login",  "-c"]

ARG USERNAME=developer
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
  && useradd -s /bin/bash --uid $USER_UID --gid $USER_GID -m $USERNAME

USER developer

ENV PATH="${PATH}:/home/developer/.local/bin"

RUN pip install pipx \
    && pipx install poetry