# In order for this Dockerfile to work it needs to be built from the `services` directory
FROM python:3.11-alpine3.18

ARG CW_GROUP_CI_TOKEN

ENV PYTHONUNBUFFERED=1

# Install python/pip
RUN apk add --update --no-cache git curl build-base libffi-dev
RUN python -m ensurepip
RUN python -m pip install --no-cache --upgrade pip setuptools poetry pip-autoremove && ln -sf pip3 /usr/bin/pip

# Create Working directory `/service` and copy `processor`
RUN mkdir /service
COPY processor/pyproject.toml /service/pyproject.toml
WORKDIR /service

# Install dependencies with poetry
RUN poetry config virtualenvs.create false
# Pass gitlab token so we can reference our local ayon-python-api repo
# as a dependency package
RUN git config --global url."https://dl:${CW_GROUP_CI_TOKEN}@gitlab.alkemy-x.com/".insteadOf "https://gitlab.alkemy-x.com/" \
  && poetry install --no-interaction --no-ansi --only main

# Remove unnecessary packages to make the image smaller
RUN apk del git curl build-base libffi-dev
RUN python -m pip cache purge
RUN pip-autoremove -y setuptools poetry
RUN python -m pip uninstall -y pip pip-autoremove

# Create a group and user: ayonuser
RUN addgroup -S ayonuser && adduser -SH ayonuser -G ayonuser

RUN chown ayonuser:ayonuser -R /service
RUN chmod 777 -R /service

COPY processor/processor /service/processor
COPY shotgrid_common /service

# Tell docker that all future commands should run as the appuser user
USER ayonuser

CMD ["python", "-m", "processor"]

