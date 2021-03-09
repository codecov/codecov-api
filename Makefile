ssh_private_key = `cat ~/.ssh/codecov-io_rsa`

build:
	docker build -f Dockerfile . -t codecov/api:latest --build-arg SSH_PRIVATE_KEY="${ssh_private_key}"

build.enterprise:
	docker build -f Dockerfile.enterprise . -t codecov/enterprise-api:latest


test:
	python -m pytest --cov=./

test.unit:
	python -m pytest --cov=./ -m "not integration" --cov-report=xml:unit.coverage.xml

test.integration:
	python -m pytest --cov=./ -m "integration" --cov-report=xml:integration.coverage.xml
