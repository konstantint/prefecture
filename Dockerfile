FROM prefecthq/prefect:3.7.0-python3.14

RUN pip install uv

RUN --mount=type=bind,source=.,target=/src \
    cd /src && uv pip install --system .

