# Formal offline DM8 backend image. Build with the repository root as context:
# docker build -f backend/Dockerfile.dm --build-arg BACKEND_RUNTIME_IMAGE=<approved-image@sha256:...> .
ARG BACKEND_RUNTIME_IMAGE
FROM ${BACKEND_RUNTIME_IMAGE}

LABEL org.opencontainers.image.title="lims-backend" \
      org.opencontainers.image.vendor="示例检测科技有限公司"

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AUTO_BOOTSTRAP=0
WORKDIR /opt/lims/app

# BACKEND_RUNTIME_IMAGE is produced/approved by the target platform and already
# contains Python, libaio, Chinese fonts and approved WPS/LibreOffice. The
# wheelhouse is reviewed offline and must contain DM-client-matched drivers.
COPY backend/requirements.txt /tmp/requirements.txt
COPY vendor/wheelhouse/ /tmp/wheelhouse/
RUN python -m pip install --no-index --find-links=/tmp/wheelhouse -r /tmp/requirements.txt \
    && python -m pip install --no-index /tmp/wheelhouse/dmPython-*.whl /tmp/wheelhouse/dmSQLAlchemy-*.whl \
    && rm -rf /tmp/wheelhouse

COPY backend/ /opt/lims/app/
RUN useradd --system --uid 10001 --home /nonexistent --shell /sbin/nologin lims \
    && chown -R 10001:0 /opt/lims/app
USER 10001
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--threads", "2", "--timeout", "180", "run:app"]
