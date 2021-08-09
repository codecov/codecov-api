from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect

from utils.config import get_config
from utils.services import get_long_service_name

from ..helpers import decode_token_from_cookie
from ..models import Session


def delete_session(request, service):
    encoded_cookie = request.COOKIES.get(f"{service}-token")
    if encoded_cookie:
        secret = get_config("setup", "http", "cookie_secret")
        token = decode_token_from_cookie(secret, encoded_cookie)
        Session.objects.filter(token=token).delete()


def logout_view(request, service):
    service_name = get_long_service_name(service)
    response = redirect("/")
    delete_session(request, service_name)
    logout(request)
    kwargs_cookie = dict(
        domain=settings.COOKIES_DOMAIN, samesite=settings.COOKIE_SAME_SITE
    )
    response.delete_cookie("staff_user", **kwargs_cookie)
    response.delete_cookie(f"{service_name}-username", **kwargs_cookie)
    response.delete_cookie(f"{service_name}-token", **kwargs_cookie)
    # temporary as we use to set cookie to Strict SameSite; but we need Lax
    # So we need delete in both samesite Strict / Lax for a little while
    kwargs_cookie = dict(domain=settings.COOKIES_DOMAIN, samesite="Strict")
    response.delete_cookie("staff_user", **kwargs_cookie)
    response.delete_cookie(f"{service_name}-username", **kwargs_cookie)
    response.delete_cookie(f"{service_name}-token", **kwargs_cookie)
    return response
