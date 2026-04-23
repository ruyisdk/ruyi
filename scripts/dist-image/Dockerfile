# syntax=docker/dockerfile:1

ARG TARGETARCH

# glibc baseline is 2.36 for x86_64 and arm64, which is Debian 12.
# However Debian 12 does not support riscv64, so make it deepin 25 instead,
# for the slightly lower glibc baseline (2.38).
FROM --platform=linux/amd64 debian:12 AS base-amd64
FROM --platform=linux/arm64 debian:12 AS base-arm64
FROM --platform=linux/riscv64 linuxdeepin/deepin:crimson-riscv64 AS base-riscv64

FROM base-$TARGETARCH
ARG TARGETARCH
ARG BUILDER_UID=1000
ARG BUILDER_GID=1000

COPY --link ./prepare-distro.sh /x/
RUN /x/prepare-distro.sh
COPY --link ./build-python.sh /x/
RUN /x/build-python.sh
COPY --link ./prepare-poetry.sh /x/
RUN /x/prepare-poetry.sh

USER $BUILDER_UID:$BUILDER_GID
WORKDIR /home/b
