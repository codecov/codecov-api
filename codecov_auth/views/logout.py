from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect


def logout_view(request, **kwargs):
    response = redirect("/")
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
