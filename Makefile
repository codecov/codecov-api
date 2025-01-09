sha := $(shell git rev-parse --short=7 HEAD)
long_sha := $(shell git rev-parse HEAD)
merge_sha := $(shell git merge-base HEAD^ origin/main)
release_version := `cat VERSION`
build_date ?= $(shell git show -s --date=iso8601-strict --pretty=format:%cd $$sha)
branch = $(shell git branch | grep \* | cut -f2 -d' ')
epoch := $(shell date +"%s")
AR_REPO ?= codecov/api
DOCKERHUB_REPO ?= codecov/self-hosted-api
REQUIREMENTS_TAG := requirements-v1-$(shell sha1sum requirements.txt | cut -d ' ' -f 1)-$(shell sha1sum docker/Dockerfile.requirements | cut -d ' ' -f 1)
VERSION := release-${sha}
CODECOV_UPLOAD_TOKEN ?= "notset"
CODECOV_STATIC_TOKEN ?= "notset"
TIMESERIES_ENABLED ?= "true"
CODECOV_URL ?= "https://api.codecov.io"
export DOCKER_BUILDKIT=1
export API_DOCKER_REPO=${AR_REPO}
export API_DOCKER_VERSION=${VERSION}
export CODECOV_TOKEN=${CODECOV_UPLOAD_TOKEN}
API_DOMAIN ?= api
PROXY_NETWORK ?= api_default

# Codecov CLI version to use
CODECOV_CLI_VERSION := 0.5.1

build:
	make build.requirements
	make build.app

check-for-migration-conflicts:
	python manage.py check_for_migration_conflicts

test:
	COVERAGE_CORE=sysmon python -m pytest --cov=./ --junitxml=junit.xml -o junit_family=legacy

test.unit:
	COVERAGE_CORE=sysmon python -m pytest --cov=./ -m "not integration" --cov-report=xml:unit.coverage.xml --junitxml=unit.junit.xml -o junit_family=legacy

test.integration:
	COVERAGE_CORE=sysmon python -m pytest --cov=./ -m "integration" --cov-report=xml:integration.coverage.xml --junitxml=integration.junit.xml -o junit_family=legacy

lint:
	make lint.install
	make lint.run

lint.install:
	echo "Installing..."
	pip install -Iv ruff

lint.run:
	ruff check
	ruff format

lint.check:
	echo "Linting..."
	ruff check
	echo "Formatting..."
	ruff format --check

build.requirements:
	# if docker pull succeeds, we have already build this version of
	# requirements.txt.  Otherwise, build and push a version tagged
	# with the hash of this requirements.txt
	touch .testenv
	docker pull ${AR_REPO}:${REQUIREMENTS_TAG} || docker build \
		-f docker/Dockerfile.requirements . \
		-t ${AR_REPO}:${REQUIREMENTS_TAG} \
		-t codecov/api-ci-requirements:${REQUIREMENTS_TAG}

build.local:
	docker build -f docker/Dockerfile . \
		-t ${AR_REPO}:latest \
		-t ${AR_REPO}:${VERSION} \
		--build-arg REQUIREMENTS_IMAGE=${AR_REPO}:${REQUIREMENTS_TAG} \
		--build-arg BUILD_ENV=local

build.app:
	docker build -f docker/Dockerfile . \
		-t ${AR_REPO}:latest \
		-t ${AR_REPO}:${VERSION} \
		--label "org.label-schema.vendor"="Codecov" \
		--label "org.label-schema.version"="${release_version}-${sha}" \
		--label "org.opencontainers.image.revision"="$(long_sha)" \
		--label "org.opencontainers.image.source"="github.com/codecov/codecov-api" \
		--build-arg REQUIREMENTS_IMAGE=${AR_REPO}:${REQUIREMENTS_TAG} \
		--build-arg RELEASE_VERSION=${VERSION} \
		--build-arg BUILD_ENV=cloud

build.self-hosted:
	make build.self-hosted-base
	make build.self-hosted-runtime

build.self-hosted-base:
	docker build -f docker/Dockerfile . \
		-t ${DOCKERHUB_REPO}:latest-no-dependencies \
		-t ${DOCKERHUB_REPO}:${VERSION}-no-dependencies \
		--build-arg REQUIREMENTS_IMAGE=${AR_REPO}:${REQUIREMENTS_TAG} \
		--build-arg RELEASE_VERSION=${VERSION} \
		--build-arg BUILD_ENV=self-hosted

build.self-hosted-runtime:
	docker build -f docker/Dockerfile . \
		-t ${DOCKERHUB_REPO}:latest \
		-t ${DOCKERHUB_REPO}:${VERSION} \
		--label "org.label-schema.vendor"="Codecov" \
		--label "org.label-schema.version"="${release_version}-${sha}" \
		--build-arg REQUIREMENTS_IMAGE=${AR_REPO}:${REQUIREMENTS_TAG} \
        --build-arg RELEASE_VERSION=${VERSION} \
        --build-arg BUILD_ENV=self-hosted-runtime

tag.latest:
	docker tag ${AR_REPO}:${VERSION} ${AR_REPO}:latest

tag.staging:
	docker tag ${AR_REPO}:${VERSION} ${AR_REPO}:staging-${VERSION}

tag.production:
	docker tag ${AR_REPO}:${VERSION} ${AR_REPO}:production-${VERSION}

tag.self-hosted-rolling:
	docker tag ${DOCKERHUB_REPO}:${VERSION}-no-dependencies ${DOCKERHUB_REPO}:rolling_no_dependencies
	docker tag ${DOCKERHUB_REPO}:${VERSION} ${DOCKERHUB_REPO}:rolling

tag.self-hosted-release:
	docker tag ${DOCKERHUB_REPO}:${VERSION}-no-dependencies ${DOCKERHUB_REPO}:${release_version}_no_dependencies
	docker tag ${DOCKERHUB_REPO}:${VERSION}-no-dependencies ${DOCKERHUB_REPO}:latest_calver_no_dependencies
	docker tag ${DOCKERHUB_REPO}:${VERSION}-no-dependencies ${DOCKERHUB_REPO}:latest_stable_no_dependencies
	docker tag ${DOCKERHUB_REPO}:${VERSION} ${DOCKERHUB_REPO}:${release_version}
	docker tag ${DOCKERHUB_REPO}:${VERSION} ${DOCKERHUB_REPO}:latest-stable
	docker tag ${DOCKERHUB_REPO}:${VERSION} ${DOCKERHUB_REPO}:latest-calver

load.requirements:
	docker load --input requirements.tar
	docker tag codecov/api-ci-requirements:${REQUIREMENTS_TAG} ${AR_REPO}:${REQUIREMENTS_TAG}

load.self-hosted:
	docker load --input self-hosted-runtime.tar
	docker load --input self-hosted.tar

save.app:
	docker save -o app.tar ${AR_REPO}:${VERSION}

save.requirements:
	docker tag ${AR_REPO}:${REQUIREMENTS_TAG} codecov/api-ci-requirements:${REQUIREMENTS_TAG}
	docker save -o requirements.tar codecov/api-ci-requirements:${REQUIREMENTS_TAG}

save.self-hosted:
	make save.self-hosted-base
	make save.self-hosted-runtime

save.self-hosted-base:
	docker save -o self-hosted.tar ${DOCKERHUB_REPO}:${VERSION}-no-dependencies

save.self-hosted-runtime:
	docker save -o self-hosted-runtime.tar ${DOCKERHUB_REPO}:${VERSION}

push.latest:
	docker push ${AR_REPO}:latest

push.staging:
	docker push ${AR_REPO}:staging-${VERSION}

push.production:
	docker push ${AR_REPO}:production-${VERSION}

push.requirements:
	docker push ${AR_REPO}:${REQUIREMENTS_TAG}

push.self-hosted-release:
	docker push ${DOCKERHUB_REPO}:${release_version}_no_dependencies
	docker push ${DOCKERHUB_REPO}:latest_calver_no_dependencies
	docker push ${DOCKERHUB_REPO}:latest_stable_no_dependencies
	docker push ${DOCKERHUB_REPO}:${release_version}
	docker push ${DOCKERHUB_REPO}:latest-stable
	docker push ${DOCKERHUB_REPO}:latest-calver

push.self-hosted-rolling:
	docker push ${DOCKERHUB_REPO}:rolling_no_dependencies
	docker push ${DOCKERHUB_REPO}:rolling

shell:
	docker-compose exec api bash
	
test_env.up:
	env | grep GITHUB > .testenv; true
	TIMESERIES_ENABLED=${TIMESERIES_ENABLED} docker-compose up -d

test_env.prepare:
	docker-compose exec api make test_env.container_prepare

test_env.check_db:
	docker-compose exec api make test_env.container_check_db
	make test_env.check-for-migration-conflicts

test_env.install_cli:
	pip install codecov-cli==$(CODECOV_CLI_VERSION)

test_env.container_prepare:
	apt-get -y install git build-essential netcat-traditional
	make test_env.install_cli
	git config --global --add safe.directory /app

test_env.container_check_db:
	while ! nc -vz postgres 5432; do sleep 1; echo "waiting for postgres"; done
	while ! nc -vz timescale 5432; do sleep 1; echo "waiting for timescale"; done

test_env.run_unit:
	docker-compose exec api make test.unit

test_env.run_integration:
	#docker-compose exec api make test.integration
	echo "Skipping. No Tests"

test_env.check-for-migration-conflicts:
	docker-compose exec api python manage.py check_for_migration_conflicts

test_env.upload:
	docker-compose exec api make test_env.container_upload CODECOV_UPLOAD_TOKEN=${CODECOV_UPLOAD_TOKEN} CODECOV_URL=${CODECOV_URL}
	docker-compose exec api make test_env.container_upload_test_results CODECOV_UPLOAD_TOKEN=${CODECOV_UPLOAD_TOKEN} CODECOV_URL=${CODECOV_URL}

test_env.container_upload:
	codecovcli -u ${CODECOV_URL} upload-process --flag unit-latest-uploader --flag unit  \
	--coverage-files-search-exclude-folder=graphql_api/types/** \
	--coverage-files-search-exclude-folder=api/internal/tests/unit/views/cassetes/**

test_env.container_upload_test_results:
	codecovcli -u ${CODECOV_URL} do-upload --report-type "test_results" \
	--files-search-exclude-folder=graphql_api/types/** \
	--files-search-exclude-folder=api/internal/tests/unit/views/cassetes/** || true

test_env.static_analysis:
	docker-compose exec api make test_env.container_static_analysis CODECOV_STATIC_TOKEN=${CODECOV_STATIC_TOKEN}

test_env.label_analysis:
	docker-compose exec api make test_env.container_label_analysis CODECOV_STATIC_TOKEN=${CODECOV_STATIC_TOKEN}

test_env.ats:
	docker-compose exec api make test_env.container_ats CODECOV_UPLOAD_TOKEN=${CODECOV_UPLOAD_TOKEN}

test_env.container_static_analysis:
	codecovcli -u ${CODECOV_URL} static-analysis --token=${CODECOV_STATIC_TOKEN}

test_env.container_label_analysis:
	codecovcli -u ${CODECOV_URL} label-analysis --base-sha=${merge_sha} --token=${CODECOV_STATIC_TOKEN}

test_env.container_ats:
	codecovcli -u ${CODECOV_URL} --codecov-yml-path=codecov_cli.yml upload-process --plugin pycoverage --plugin compress-pycoverage --flag smart-labels --fail-on-error

test_env:
	make test_env.up
	make test_env.prepare
	make test_env.check_db
	make test_env.run_unit
	make test_env.check-for-migration-conflicts


### START Proxy Commands
.PHONY: proxy.build
proxy.build: # Used to build the proxy
proxy.build:
	docker build -f docker/Dockerfile-proxy . -t ${API_DOCKER_REPO}/proxy:latest -t ${API_DOCKER_REPO}/proxy:${release_version}-${sha} \
			--label "org.label-schema.build-date"="$(build_date)" \
			--label "org.label-schema.name"="API Proxy" \
			--label "org.label-schema.vendor"="api" \
			--label "org.label-schema.version"="${release_version}"

.PHONY: proxy.run
proxy.run: # Used to run the proxy
proxy.run:
	make proxy.build
	make proxy.down
	docker run --rm --network ${PROXY_NETWORK} -e FRP_TOKEN=${FRP_TOKEN} -e DOMAIN=${API_DOMAIN} --name api-proxy ${API_DOCKER_REPO}/proxy:latest
	sleep 3
	make proxy.logs
	# You should see "[api] start proxy success"
	# If no logs then proxy failed to start. Check if you are on VPN. If you get a 404, check if you are on VPN

.PHONY: proxy.logs
proxy.logs: # Used to logs the proxy
proxy.logs:
	docker logs api-proxy

.PHONY: proxy.shell
proxy.shell: # Used to shell the proxy
proxy.shell:
	docker exec -it api-proxy sh

.PHONY: proxy.down
proxy.down: # Used to down the proxy
proxy.down:
	docker kill api-proxy || true

### END PROXY Commands
