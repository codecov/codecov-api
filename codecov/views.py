from django.http import HttpResponse, HttpResponseRedirect
from django.conf import settings

def health(request):
    return HttpResponse("api is live!")

def redirect_app(request):
    """
    This view is intended to be used as part of the frontend migration to redirect traffic from legacy urls to urls 
    """
    app_domain = settings.CODECOV_DASHBOARD_URL
    return HttpResponseRedirect(app_domain + request.path.replace("/redirect_app", ""))
