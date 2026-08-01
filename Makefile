# Tennis Buddy — short-balls (tennis reels) helpers
#
# Usage:
#   make              # same as make help
#   make build        # build the tennis-reels image
#   make run          # process ./short-balls/inputs → ./short-balls/reels
#   make dry-run      # analyse only; write cut-list CSV, no encoding
#   make run ARGS='--keep 0.4 --mute'
#   make run INPUT=inputs/1.MP4
#   make shell        # interactive shell in the container

SHORT_BALLS := short-balls
COMPOSE     := docker compose --project-directory $(SHORT_BALLS) -f $(SHORT_BALLS)/docker-compose.yml
SERVICE     := tennis-reels

# Default input path inside the container (host: short-balls/inputs)
INPUT ?= inputs
ARGS  ?=

.PHONY: help build run dry-run shell

help:
	@echo "short-balls targets:"
	@echo "  make build              Build the tennis-reels Docker image"
	@echo "  make run                Encode reels from short-balls/inputs"
	@echo "  make dry-run            Analyse + cut-list CSV only (no encode)"
	@echo "  make shell              Open a shell in the container"
	@echo ""
	@echo "Variables:"
	@echo "  INPUT=inputs            Input file or folder (container path)"
	@echo "  ARGS='--keep 0.4'       Extra flags passed to tennis_reels.py"
	@echo ""
	@echo "Examples:"
	@echo "  make run"
	@echo "  make dry-run INPUT=inputs/1.MP4"
	@echo "  make run ARGS='--keep 0.4 --mute --encoder libx264'"

build:
	$(COMPOSE) build

run:
	$(COMPOSE) run --rm $(SERVICE) -i $(INPUT) $(ARGS)

dry-run:
	$(COMPOSE) run --rm $(SERVICE) -i $(INPUT) --dry-run $(ARGS)

shell:
	$(COMPOSE) run --rm --entrypoint /bin/sh $(SERVICE)
