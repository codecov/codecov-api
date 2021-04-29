ssh_private_key = `cat ~/.ssh/codecov-io_rsa`
sha := $(shell git rev-parse --short=7 HEAD)
release_version = `cat VERSION`


build:
	docker build -f Dockerfile . -t codecov/api:latest --build-arg SSH_PRIVATE_KEY="${ssh_private_key}"

build.enterprise:
	docker build -f Dockerfile.enterprise . -t codecov/enterprise-api:${release_version}

build.enterprise-private:
	docker build -f Dockerfile.enterprise . -t codecov/api-private:${release_version}-${sha}

check-for-migration-conflicts:
	python manage.py check_for_migration_conflicts

push.enterprise:
	docker push codecov/enterprise-api:${release_version}
	docker tag codecov/enterprise-api:${release_version} codecov/enterprise-api:latest-stable
	docker push codecov/enterprise-api:latest-stable


push.enterprise-private:
	docker push codecov/api-private:${release_version}-${sha}

test:
	python -m pytest --cov=./

test.unit:
	python -m pytest --cov=./ -m "not integration" --cov-report=xml:unit.coverage.xml

test.integration:
	python -m pytest --cov=./ -m "integration" --cov-report=xml:integration.coverage.xml
