FROM python:3.10
ENV PATH="~/.local/bin:${PATH}"

# get poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /app

COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock
COPY README.md README.md

# install dependencies
RUN ~/.local/bin/poetry install --no-root --with develop --without datasets

COPY heinlein /app/heinlein
COPY datasets /app/datasets
# Install the datasets
# loop through the datasets and install them

RUN ~/.local/bin/poetry install --with datasets

COPY ./tests /app/tests

RUN mv /app/tests/run_tests.sh /app/run_tests.sh
RUN chmod +x run_tests.sh

CMD ["./run_tests.sh"]
