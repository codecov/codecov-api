short_services = {"gh": "github", "bb": "bitbucket", "gl": "gitlab"}
long_services = {value: key for (key, value) in short_services.items()}


def get_long_service_name(service):
    if service in short_services:
        return short_services[service]
    return service


def get_short_service_name(service):
    if service in long_services:
        return long_services[service]
    return service
