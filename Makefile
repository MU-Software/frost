PORT ?= 8808
HOST ?= 0.0.0.0

MIGRATION_MESSAGE ?= `date +"%Y%m%d_%H%M%S"`
UPGRADE_VERSION ?= head
DOWNGRADE_VERSION ?= -1

MKFILE_PATH := $(abspath $(lastword $(MAKEFILE_LIST)))
PROJECT_DIR := $(dir $(MKFILE_PATH))

ifeq (docker-build,$(firstword $(MAKECMDGOALS)))
  IMAGE_NAME := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
  $(eval $(IMAGE_NAME):;@:)
endif
IMAGE_NAME := $(if $(IMAGE_NAME),$(IMAGE_NAME),frost_image)

ifeq (env-generate,$(firstword $(MAKECMDGOALS)))
  ENV_JSON_FILE := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
  $(eval $(ENV_JSON_FILE):;@:)
else ifeq (env-force-generate,$(firstword $(MAKECMDGOALS)))
  ENV_JSON_FILE := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
  $(eval $(ENV_JSON_FILE):;@:)
endif
ENV_JSON_FILE := $(if $(ENV_JSON_FILE),$(ENV_JSON_FILE),dev.json)

.ONESHELL:

goto-frost-dir:
	@cd $(PROJECT_DIR)

# Docker related
docker-up: ENV_JSON_FILE = docker_dev.json
docker-up: goto-frost-dir env-generate swagger-ui-download
	docker-compose \
		--project-directory ${PROJECT_DIR}docker \
		--env-file ${PROJECT_DIR}.env \
		build \
		--build-arg INVALIDATE_CACHE_DATE=$(shell date +%Y-%m-%d_%H:%M:%S)
	docker-compose \
		--project-directory ${PROJECT_DIR}docker \
		--env-file ${PROJECT_DIR}.env \
		up -d

docker-up-debug: ENV_JSON_FILE = docker_dev.json
docker-up-debug: goto-frost-dir env-force-generate swagger-ui-force-download
	docker-compose \
		--project-directory ${PROJECT_DIR}docker \
		--env-file ${PROJECT_DIR}.env \
		build \
		--build-arg INVALIDATE_CACHE_DATE=$(shell date +%Y-%m-%d_%H:%M:%S) \
		--no-cache --progress=plain 2>&1 | tee docker-compose-build.log
	docker-compose \
		--project-directory ${PROJECT_DIR}docker \
		--env-file ${PROJECT_DIR}.env \
		up -d

docker-stop: goto-frost-dir
	docker-compose \
		--project-directory ${PROJECT_DIR}docker \
		--env-file ${PROJECT_DIR}.env \
		stop

docker-rm: goto-frost-dir docker-stop
	docker-compose \
		--project-directory ${PROJECT_DIR}docker \
		--env-file ${PROJECT_DIR}.env \
		rm

docker-build: ENV_JSON_FILE = docker_dev.json
docker-build: goto-frost-dir env-generate swagger-ui-download
	docker build \
		--target runtime \
		-f ${PROJECT_DIR}docker/Dockerfile \
		-t $(IMAGE_NAME) \
		--build-arg INVALIDATE_CACHE_DATE=$(shell date +%Y-%m-%d_%H:%M:%S) \
		$(PROJECT_DIR)

docker-build-debug: ENV_JSON_FILE = docker_dev.json
docker-build-debug: goto-frost-dir env-generate swagger-ui-force-download
	docker build \
		--progress=plain \
		--no-cache \
		--target runtime \
		-f ${PROJECT_DIR}docker/Dockerfile \
		-t $(IMAGE_NAME) \
		--build-arg INVALIDATE_CACHE_DATE=$(shell date +%Y-%m-%d_%H:%M:%S) \
		$(PROJECT_DIR) 2>&1 | tee docker-build.log

docker-ps: goto-frost-dir
	docker-compose \
		--project-directory ${PROJECT_DIR}docker \
		--env-file ${PROJECT_DIR}.env \
		ps

docker-shell-bash: goto-frost-dir
		docker exec -it $(shell \
			docker-compose \
				--project-directory ${PROJECT_DIR}docker \
				--env-file ${PROJECT_DIR}.env \
				ps -q frost-api-server \
		) /bin/bash

docker-shell-plus: goto-frost-dir
		docker exec -it $(shell \
			docker-compose \
				--project-directory ${PROJECT_DIR}docker \
				--env-file ${PROJECT_DIR}.env \
				ps -q frost-api-server \
		) /usr/local/bin/flask shell-plus

docker-shell: goto-frost-dir docker-shell-bash
docker-sp: goto-frost-dir docker-shell-plus

# DB management related (not released yet)
# db-makemigrations: goto-frost-dir
# 	poetry run flask db revision --autogenerate -m $(MIGRATION_MESSAGE)

# db-upgrade: goto-frost-dir
# 	poetry run flask db upgrade $(UPGRADE_VERSION)

# db-downgrade: goto-frost-dir
# 	poetry run flask db downgrade $(DOWNGRADE_VERSION)

# db-reset: goto-frost-dir
# 	poetry run flask db downgrade base

db-erd-export: goto-frost-dir
	poetry run flask draw-db-erd

# Dependency management related
dep-install: goto-frost-dir
	poetry install --no-root --with dev

dep-upgrade: goto-frost-dir
	poetry update

dep-lock: goto-frost-dir
	poetry lock --no-update

dep-export: goto-frost-dir
	poetry export -f requirements.txt --without-hashes --without=dev --output requirements.txt
	poetry export -f requirements.txt --without-hashes --output requirements-dev.txt

build: goto-frost-dir dep-install hooks-install docker-up

# Runserver related
runserver-flask: goto-frost-dir dep-install
	poetry run flask run

runserver-gunicorn: goto-frost-dir dep-install
	poetry run gunicorn --host $(HOST) --port $(PORT) --reload app.main:app

runserver: goto-frost-dir runserver-flask

# Devtools
hooks-install: goto-frost-dir
	poetry run pre-commit install

lint: goto-frost-dir
	poetry run pre-commit run --all-files

openapi-export: goto-frost-dir
	flask create-openapi-doc

swagger-ui-download: goto-frost-dir
	@if test -f swagger_ui_dist/index.html; then \
		echo "swagger-ui already downloaded!"; \
	else \
		mkdir -p swagger_ui_dist; \
		curl 'https://api.github.com/repos/swagger-api/swagger-ui/releases/latest' \
			| jq '.["zipball_url"]' \
			| xargs curl -L --max-redirs 5 \
			| tar xvz --strip=2 -C swagger_ui_dist 'swagger-api-swagger-ui-*/dist/*'; \
		rm -rf swagger_ui_dist/swagger-ui-react/; \
	fi

swagger-ui-force-download: goto-frost-dir
	rm -rf swagger_ui_dist;
	mkdir -p swagger_ui_dist;
	curl 'https://api.github.com/repos/swagger-api/swagger-ui/releases/latest' \
		| jq '.["zipball_url"]' \
		| xargs curl -L --max-redirs 5 \
		| tar xvz --strip=2 -C swagger_ui_dist 'swagger-api-swagger-ui-*/dist/*';
	rm -rf swagger_ui_dist/swagger-ui-react/;

env-force-generate: goto-frost-dir
	poetry run python ./env_collection/env_creator.py -o "$(ENV_JSON_FILE)";

env-generate: goto-frost-dir
	@if test -f .env; then \
		echo ".env file already exists!"; \
	else \
		poetry run python ./env_collection/env_creator.py -o "$(ENV_JSON_FILE)"; \
	fi

# test: goto-frost-dir dep-install docker-up
# 	poetry run pytest
