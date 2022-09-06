from django.http import JsonResponse
from rest_framework import status


def not_found(request, *args, **kwargs):
    data = {"error": "Page Not Found (404)"}
    return JsonResponse(data=data, status=status.HTTP_404_NOT_FOUND)
