from apps.accounts.permissions import ordered_roles

SESSION_KEY = "active_role"


class ActiveRoleMiddleware:
    """Sets request.active_role and request.available_roles (spec §4.8).
    The active role picks the home page and navbar only; access is decided by memberships."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.active_role = None
        request.available_roles = []
        if request.user.is_authenticated:
            roles = ordered_roles(request.user)
            chosen = request.session.get(SESSION_KEY)
            if chosen not in roles:
                chosen = roles[0] if roles else None
                if chosen:
                    request.session[SESSION_KEY] = chosen
                else:
                    request.session.pop(SESSION_KEY, None)
            request.active_role = chosen
            request.available_roles = roles
        return self.get_response(request)
