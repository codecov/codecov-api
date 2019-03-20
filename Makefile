ssh_private_key = `cat ~/.ssh/codecov-io_rsa`

build:
	docker build -f Dockerfile . -t codecov/api:latest --build-arg SSH_PRIVATE_KEY="${ssh_private_key}"