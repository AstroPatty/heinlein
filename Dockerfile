FROM python:3.11
ENV PATH="~/.local/bin:${PATH}"

# get poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# copy library into container
COPY pyproject.toml /app/pyproject.toml
COPY poetry.lock /app/poetry.lock
COPY README.md /app/README.md
COPY heinlein /app/heinlein
COPY datasets /app/datasets

WORKDIR /app
# install dependencies
RUN ~/.local/bin/poetry install --with develop

# Install the datasets
# loop through the datasets and install them


COPY ./tests /app/tests

RUN mv /app/tests/run_tests.sh /app/run_tests.sh
RUN chmod +x run_tests.sh

CMD ["./run_tests.sh"]
