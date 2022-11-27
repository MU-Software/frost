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
docker-up: goto-frost-dir env-generate
	docker-compose \
		--project-directory ${PROJECT_DIR}docker \
		--env-file ${PROJECT_DIR}.env \
		build
	docker-compose \
		--project-directory ${PROJECT_DIR}docker \
		--env-file ${PROJECT_DIR}.env \
		up -d

docker-up-debug: ENV_JSON_FILE = docker_dev.json
docker-up-debug: goto-frost-dir env-generate
	docker-compose \
		--project-directory ${PROJECT_DIR}docker \
		--env-file ${PROJECT_DIR}.env \
		build \
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

docker-up: ENV_JSON_FILE = docker_dev.json
docker-build: goto-frost-dir env-generate
	docker build \
		--target runtime \
		-f ${PROJECT_DIR}docker/Dockerfile \
		-t $(IMAGE_NAME) \
		$(PROJECT_DIR)

docker-up: ENV_JSON_FILE = docker_dev.json
docker-build-debug: goto-frost-dir env-generate
	docker build \
		--progress=plain \
		--no-cache \
		--target runtime \
		-f ${PROJECT_DIR}docker/Dockerfile \
		-t $(IMAGE_NAME) $(PROJECT_DIR) 2>&1 | tee docker-build.log

# DB management related (not released yet)
# db-makemigrations: goto-frost-dir
# 	poetry run alembic revision --autogenerate -m $(MIGRATION_MESSAGE)

# db-upgrade: goto-frost-dir
# 	poetry run alembic upgrade $(UPGRADE_VERSION)

# db-downgrade: goto-frost-dir
# 	poetry run alembic downgrade $(DOWNGRADE_VERSION)

# db-reset: goto-frost-dir
# 	poetry run alembic downgrade base

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

build: goto-frost-dir deps-install hooks-install docker-up db-upgrade

# Runserver related
runserver-flask: goto-frost-dir deps-install docker-up
	poetry run flask run

runserver-gunicorn: goto-frost-dir deps-install docker-up
	poetry run gunicorn --host $(HOST) --port $(PORT) --reload app.main:app

runserver: goto-frost-dir runserver-flask

# Devtools
hooks-install: goto-frost-dir
	poetry run pre-commit install

lint: goto-frost-dir
	poetry run pre-commit run --all-files

openapi-export: goto-frost-dir
	poetry run flask create-openapi-doc

env-force-generate: goto-frost-dir
	poetry run python ./env_collection/env_creator.py -o "$(ENV_JSON_FILE)";

env-generate: goto-frost-dir
	@if test -f .env; then \
		echo ".env file already exists!"; \
	else \
		poetry run python ./env_collection/env_creator.py -o "$(ENV_JSON_FILE)"; \
	fi

# test: goto-frost-dir deps-install docker-up
# 	poetry run pytest
