FROM ubuntu:22.04

ARG BUILDER_UID=1000
ARG BUILDER_GID=1000

COPY ./prepare-distro.sh /tmp/prepare-distro.sh
RUN /tmp/prepare-distro.sh

USER $BUILDER_UID:$BUILDER_GID
WORKDIR /home/b
