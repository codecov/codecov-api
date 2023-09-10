sha := $(shell git rev-parse --short=7 HEAD)
release_version = `cat VERSION`
build_date ?= $(shell git show -s --date=iso8601-strict --pretty=format:%cd $$sha)
branch = $(shell git branch | grep \* | cut -f2 -d' ')
epoch := $(shell date +"%s")
AR_REPO ?= codecov/self-hosted-api
REQUIREMENTS_TAG := requirements-v1-$(shell sha1sum requirements.txt | cut -d ' ' -f 1)-$(shell sha1sum Dockerfile.requirements | cut -d ' ' -f 1)
VERSION := release-$(shell git rev-parse --short=7 HEAD)
export DOCKER_BUILDKIT=1
export API_DOCKER_REPO=${AR_REPO}
export API_DOCKER_VERSION=${VERSION}


build.enterprise_runtime:
	# $(MAKE) build.enterprise
	docker build -f Dockerfile.enterprise_runtime . -t codecov/api-enterprise-runtime:${release_version} \
		--build-arg CODECOV_ENTERPRISE_RELEASE=codecov/enterprise-api:${release_version} \
		--build-arg RELEASE_VERSION=${release_version} \
		--label "org.label-schema.build-date"="$(build_date)" \
		--label "org.label-schema.name"="Self-Hosted API" \
		--label "org.label-schema.vendor"="Codecov" \
		--label "org.label-schema.version"="${release_version}"
	docker tag codecov/api-enterprise-runtime:${release_version} codecov/api-enterprise-runtime:latest-stable

build.enterprise:
	$(MAKE) build
	docker build -f Dockerfile.enterprise . -t codecov/enterprise-api:${release_version} \
		--label "org.label-schema.build-date"="$(build_date)" \
		--label "org.label-schema.name"="Self-Hosted API (no dependencies)" \
		--label "org.label-schema.vendor"="Codecov" \
		--label "org.label-schema.version"="${release_version}"
	docker tag codecov/enterprise-api:${release_version} codecov/enterprise-api:latest-stable



build.enterprise-private:
	docker build -f Dockerfile.enterprise . -t codecov/enterprise-private-api:${release_version}-${sha} \
		--label "org.label-schema.build-date"="$(build_date)" \
		--label "org.label-schema.name"="Self-Hosted API Private" \
		--label "org.label-schema.vendor"="Codecov" \
		--label "org.label-schema.version"="${release_version}-${sha}" \
		--label "org.vcs-branch"="$(branch)"

run.enterprise:
	docker-compose -f docker-compose-enterprise.yml up -d

enterprise:
	$(MAKE) build.enterprise
	$(MAKE) run.enterprise

check-for-migration-conflicts:
	python manage.py check_for_migration_conflicts

test:
	python -m pytest --cov=./

test.unit:
	python -m pytest --cov=./ -m "not integration" --cov-report=xml:unit.coverage.xml

test.integration:
	python -m pytest --cov=./ -m "integration" --cov-report=xml:integration.coverage.xml

lint.install:
	echo "Installing..."
	pip install -Iv black==22.3.0 isort

lint.run:
	black .
	isort --profile black .

lint.check:
	echo "Linting..."
	black --check .
	echo "Sorting..."
	isort --profile black --check .

build.requirements:
	# if docker pull succeeds, we have already build this version of
	# requirements.txt.  Otherwise, build and push a version tagged
	# with the hash of this requirements.txt
	docker pull ${AR_REPO}:${REQUIREMENTS_TAG} || docker build \
		-f docker/Dockerfile.requirements . \
		-t ${AR_REPO}:${REQUIREMENTS_TAG}

build.app:
	docker build -f docker/Dockerfile . \
		-t ${AR_REPO}:latest \
		-t ${AR_REPO}:${VERSION} \
		--build-arg REQUIREMENTS_IMAGE=${AR_REPO}:${REQUIREMENTS_TAG}

build:
	make build.requirements
	make build.app

tag.latest:
	docker tag ${AR_REPO}:${VERSION} ${AR_REPO}:latest

tag.staging:
	docker tag ${AR_REPO}:${VERSION} ${AR_REPO}:staging-${VERSION}

tag.production:
	docker tag ${AR_REPO}:${VERSION} ${AR_REPO}:production-${VERSION}

save.app:
	docker save -o app.tar ${AR_REPO}:${VERSION}

push.staging:
	docker push ${AR_REPO}:staging-${VERSION}

push.production:
	docker push ${AR_REPO}:production-${VERSION}

push.requirements:
	docker push ${AR_REPO}:${REQUIREMENTS_TAG}

test_env.up:
	docker-compose -f docker-compose-test.yml up -d

test_env.prepare:
	docker-compose -f docker-compose-test.yml exec api make test_env.container_prepare

test_env.check_db:
	docker-compose -f docker-compose-test.yml exec api make test_env.container_check_db

test_env.container_prepare:
	apk add -U curl git build-base
	pip install codecov-cli

test_env.container_check_db:
	while ! nc -vz postgres 5432; do sleep 1; echo "waiting for postgres"; done
	while ! nc -vz timescale 5432; do sleep 1; echo "waiting for timescale"; done

test_env.run_unit:
	docker-compose -f docker-compose-test.yml exec api make test.unit

test_env.check-for-migration-conflicts:
	docker-compose -f docker-compose-test.yml exec api python manage.py check_for_migration_conflicts

test_env:
	make test_env.up
	make test_env.prepare
	make test_env.check_db
	make test_env.run_unit
	make test_env.check-for-migration-conflicts