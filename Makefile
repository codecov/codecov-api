build.base:
	docker build -f Dockerfile.base -t codecov/api-base:latest .

build.dev:
	docker build -f Dockerfile.development -t codecov/api-dev:latest .

build.prod:
	docker build -f Dockerfile.production -t codecov/api:latest .