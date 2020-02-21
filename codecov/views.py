from django.http import HttpResponse

from core.models import Version

def health(request):
    version = Version.objects.last()
    return HttpResponse("%s is live!" % version.version)
