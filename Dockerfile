# Isolates the app's filesystem and network from the host, so the RCE
# challenge (see README) grants access to this disposable container, not
# your real machine. See README's "Running in Docker" section for the
# two things that undo that isolation: mounting a host volume in, or
# publishing the port beyond localhost when you don't mean to.
FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Runs as a non-root user - RCE inside the container should not even
# get root within the container's own filesystem.
RUN useradd --create-home --shell /bin/bash fakebank \
    && chown -R fakebank:fakebank /app
USER fakebank

EXPOSE 5005

# No entrypoint script needed here the way run.sh is for a bare-metal
# run: fakebank.db and .rce_flag live inside the container's own
# writable layer, so removing the container (docker rm) already wipes
# them - a fresh `docker run` always starts from a clean, freshly
# seeded database.
CMD ["python", "app.py"]
