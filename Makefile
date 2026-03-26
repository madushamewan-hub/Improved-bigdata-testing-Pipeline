start:
	@echo "Starting Docker Compose stack..."
	docker-compose -f docker/docker-compose.yml up -d

stop:
	@echo "Stopping Docker Compose stack..."
	docker-compose -f docker/docker-compose.yml down

test:
	@echo "Running pytest..."
	python -m pytest tests/ -q

experiment:
	@echo "Running experiment script..."
	python experiments/run_experiment.py
