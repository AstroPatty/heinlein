FROM python:3.10
ENV PATH="~/.local/bin:${PATH}"

# get poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# copy library into container
COPY pyproject.toml /app/pyproject.toml
COPY poetry.lock /app/poetry.lock
COPY README.md /app/README.md
COPY heinlein /app/heinlein

WORKDIR /app

# install dependencies
RUN ~/.local/bin/poetry install
RUN git clone https://github.com/esheldon/pymangle.git
RUN cd pymangle && pip install . && rm -r tests

RUN pip install heinlein_des

COPY ./tests /app/tests

RUN mv /app/tests/run_tests.sh /app/run_tests.sh
RUN chmod +x run_tests.sh

CMD ["./run_tests.sh"]
