from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class UserBurstRateThrottle(UserRateThrottle):
    scope = "user-burst"


class UserSustainedRateThrottle(UserRateThrottle):
    scope = "user-sustained"


class AnonBurstRateThrottle(AnonRateThrottle):
    scope = "anon-burst"


class AnonSustainedRateThrottle(AnonRateThrottle):
    scope = "anon-sustained"
