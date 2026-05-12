#!/bin/bash

docker compose exec prefect-worker prefect deploy --all --no-prompt
