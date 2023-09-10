sha := $(shell git rev-parse --short=7 HEAD)
long_sha := $(shell git rev-parse HEAD)
release_version := `cat VERSION`
build_date ?= $(shell git show -s --date=iso8601-strict --pretty=format:%cd $$sha)
branch = $(shell git branch | grep \* | cut -f2 -d' ')
epoch := $(shell date +"%s")
AR_REPO ?= codecov/self-hosted-api
DOCKERHUB_REPO ?= codecov/self-hosted-api
REQUIREMENTS_TAG := requirements-v1-$(shell sha1sum requirements.txt | cut -d ' ' -f 1)-$(shell sha1sum docker/Dockerfile.requirements | cut -d ' ' -f 1)
VERSION := release-${sha}
CODECOV_UPLOAD_TOKEN="notset"
export DOCKER_BUILDKIT=1
export API_DOCKER_REPO=${AR_REPO}
export API_DOCKER_VERSION=${VERSION}
export CODECOV_TOKEN=${CODECOV_UPLOAD_TOKEN}


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

build.self-hosted:
	docker build -f docker/Dockerfile.self-hosted . \
		-t ${AR_REPO}:latest-no-dependencies \
		-t ${AR_REPO}:${VERSION}-no-dependencies \
		--build-arg REQUIREMENTS_IMAGE=${AR_REPO}:${REQUIREMENTS_TAG} \
		--build-arg RELEASE_VERSION=${VERSION}

build.self-hosted-runtime:
	docker build -f Dockerfile.self-hosted-runtime . \
		-t ${DOCKERHUB_REPO}:latest \
		-t ${DOCKERHUB_REPO}:${VERSION} \
		--build-arg CODECOV_ENTERPRISE_RELEASE=${DOCKERHUB_REPO}:${VERSION}-no-dependencies \
        --build-arg RELEASE_VERSION=${VERSION}

build:
	make build.requirements
	make build.app

tag.latest:
	docker tag ${AR_REPO}:${VERSION} ${AR_REPO}:latest

tag.staging:
	docker tag ${AR_REPO}:${VERSION} ${AR_REPO}:staging-${VERSION}

tag.production:
	docker tag ${AR_REPO}:${VERSION} ${AR_REPO}:production-${VERSION}

tag.self-hosted-rolling:
	docker tag ${DOCKERHUB_REPO}:${VERSION}-no-dependencies ${DOCKERHUB_REPO}:rolling_no_dependencies
	docker tag ${DOCKERHUB_REPO}:${VERSION} ${DOCKERHUB_REPO}:rolling

tag.self-hosted:
	docker tag ${DOCKERHUB_REPO}:${VERSION}-no-dependencies ${DOCKERHUB_REPO}:${release_version}_no_dependencies
	docker tag ${DOCKERHUB_REPO}:${VERSION}-no-dependencies ${DOCKERHUB_REPO}:latest_calver_no_dependencies
	docker tag ${DOCKERHUB_REPO}:${VERSION}-no-dependencies ${DOCKERHUB_REPO}:latest_stable_no_dependencies
	docker tag ${DOCKERHUB_REPO}:${VERSION} ${DOCKERHUB_REPO}:${release_version}
	docker tag ${DOCKERHUB_REPO}:${VERSION} ${DOCKERHUB_REPO}:latest-stable
	docker tag ${DOCKERHUB_REPO}:${VERSION} ${DOCKERHUB_REPO}:latest-calver

save.app:
	docker save -o app.tar ${AR_REPO}:${VERSION}

save.requirements:
	docker save -o requirements.tar ${AR_REPO}:${REQUIREMENTS_TAG}

save.self-hosted:
	docker save -o self-hosted.tar ${DOCKERHUB_REPO}:${VERSION}-no-dependencies

save.self-hosted-runtime:
	docker save -o self-hosted-runtime.tar ${DOCKERHUB_REPO}:${VERSION}

push.staging:
	docker push ${AR_REPO}:staging-${VERSION}

push.production:
	docker push ${AR_REPO}:production-${VERSION}

push.requirements:
	docker push ${AR_REPO}:${REQUIREMENTS_TAG}

push.self-hosted:
	docker push ${DOCKERHUB_REPO}:${release_version}_no_dependencies
	docker push ${DOCKERHUB_REPO}:latest_calver_no_dependencies
	docker push ${DOCKERHUB_REPO}:latest_stable_no_dependencies
	docker push ${DOCKERHUB_REPO}:${release_version}
	docker push ${DOCKERHUB_REPO}:latest-stable
	docker push ${DOCKERHUB_REPO}:latest-calver

push.self-hosted-rolling:
	docker push ${DOCKERHUB_REPO}:rolling_no_dependencies
	docker push ${DOCKERHUB_REPO}:rolling

test_env.up:
	docker-compose -f docker-compose-test.yml up -d

test_env.prepare:
	env | grep GITHUB > .githubenv
	docker-compose -f docker-compose-test.yml exec api make test_env.container_prepare

test_env.check_db:
	docker-compose -f docker-compose-test.yml exec api make test_env.container_check_db

test_env.install_cli:
	pip install codecov-cli

test_env.container_prepare:
	apk add -U curl git build-base
	make test_env.install_cli
	git config --global --add safe.directory /app

test_env.container_check_db:
	while ! nc -vz postgres 5432; do sleep 1; echo "waiting for postgres"; done
	while ! nc -vz timescale 5432; do sleep 1; echo "waiting for timescale"; done

test_env.run_unit:
	docker-compose -f docker-compose-test.yml exec api make test.unit

test_env.check-for-migration-conflicts:
	docker-compose -f docker-compose-test.yml exec api python manage.py check_for_migration_conflicts

test_env.upload:
	docker-compose -f docker-compose-test.yml exec api make test_env.container_upload

test_env.upload_staging:
	docker-compose -f docker-compose-test.yml exec api make test_env.container_upload_staging

test_env.container_upload:
	codecovcli  do-upload --flag unit-latest-uploader --flag unit \
	--coverage-files-search-exclude-folder=graphql_api/types/** \
	--coverage-files-search-exclude-folder=api/internal/tests/unit/views/cassetes/**

test_env.container_upload_staging:
	codecovcli  do-upload --flag unit-latest-uploader --flag unit -u https://stage-api.codecov.dev \
	--coverage-files-search-exclude-folder=graphql_api/types/** \
	--coverage-files-search-exclude-folder=api/internal/tests/unit/views/cassetes/**

test_env.static_analysis:
	docker-compose -f docker-compose-test.yml exec api make test_env.container_static_analysis

test_env.label_analysis:
	docker-compose -f docker-compose-test.yml exec api make test_env.container_label_analysis

test_env.ats:
	docker-compose -f docker-compose-test.yml exec api make test_env.container_ats

test_env.container_static_analysis:
	codecovcli static-analysis

test_env.container_label_analysis:
	codecovcli label-analysis --base-sha=$(shell git merge-base HEAD^ origin/main)

test_env.container_ats:
	codecovcli --codecov-yml-path=codecov_cli.yml do-upload --plugin pycoverage --plugin compress-pycoverage --flag smart-labels --fail-on-error -r ${{ github.repository }} --git-service=github

test_env:
	make test_env.up
	make test_env.prepare
	make test_env.check_db
	make test_env.run_unit
	make test_env.check-for-migration-conflicts