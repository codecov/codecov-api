GCR_REPO := gcr.io/genuine-polymer-165712/codecov-deploy

build:
	docker build \
		-f Dockerfile.deploy \
		-t ${GCR_REPO}:latest .

push:
	docker push ${GCR_REPO}:latest
