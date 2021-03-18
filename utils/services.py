short_services = {
    'gh': 'github',
    'bb': 'bitbucket',
    'gl': 'gitlab'
}

def get_long_service_name(service):
    if service in short_services:
        return short_services[service]
    return service
