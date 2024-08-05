FROM        python:3.12.4-alpine@sha256:63094abdaf49e046da9f6529ecd6ce4d853d9bfbf00a25c52bbbb68b3223b490

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
