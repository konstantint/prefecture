#!/bin/bash

find workdir -name prefect.yaml -exec docker compose exec prefect-worker prefect deploy --all --no-prompt --prefect-file /{} \;
