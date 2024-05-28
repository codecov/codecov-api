from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpRequest
from django.shortcuts import HttpResponse, redirect
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET", "POST"])
def logout_view(request: HttpRequest, **kwargs: str) -> HttpResponse:
    if request.method == "POST":
        response = Response(status=205)
    else:
        # Preserving GET logouts until Gazebo is moved off of it.
        redirect_url = settings.CODECOV_DASHBOARD_URL
        response = redirect(redirect_url)

    logout(request)
    kwargs_cookie = dict(
        domain=settings.COOKIES_DOMAIN, samesite=settings.COOKIE_SAME_SITE
    )
    response.delete_cookie("staff_user", **kwargs_cookie)

    # temporary as we use to set cookie to Strict SameSite; but we need Lax
    # So we need delete in both samesite Strict / Lax for a little while
    kwargs_cookie = dict(domain=settings.COOKIES_DOMAIN, samesite="Strict")
    response.delete_cookie("staff_user", **kwargs_cookie)

    return response
