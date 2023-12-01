import datetime

from ariadne import ObjectType
from django.conf import settings
from shared.license import LicenseInformation

self_hosted_license_bindable = ObjectType("SelfHostedLicense")


@self_hosted_license_bindable.field("expirationDate")
def resolve_expiration_date(license: LicenseInformation, info) -> datetime.date:
    if not settings.IS_ENTERPRISE:
        return None

    return license.expires
