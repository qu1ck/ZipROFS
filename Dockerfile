FROM        python:3.12.4-alpine@sha256:2abecb741d63f6627f318377cd5886bf89069458007317488b0e9fe06d3c11f6

# renovate: datasource=repology depName=alpine_3_20/fuse versioning=loose
ARG         FUSE_VERSION="2.9.9-r5"

WORKDIR     /app

ADD         requirements.txt .

RUN         apk add --no-cache \
              fuse=${FUSE_VERSION} \
            && \
            sed -i 's/#user_allow_other/user_allow_other/g' /etc/fuse.conf && \
            pip install -r requirements.txt && \
            rm -rf /root/.cache /root/.cargo

COPY        --chown=nobody:nogroup . .

USER        nobody
ENV         FUSE_LIBRARY_PATH=/usr/lib/libfuse.so.2

ENTRYPOINT  [ "python", "./ziprofs.py" ]
