from django.http import HttpResponse

def health(request):
    return HttpResponse("api is live!")
