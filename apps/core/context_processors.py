from apps.core.navigation import ROLE_LABELS, nav_items_for


def navigation(request):
    role = getattr(request, "active_role", None)
    roles = getattr(request, "available_roles", [])
    return {
        "active_role": role,
        "active_role_label": ROLE_LABELS.get(role, ""),
        "available_roles": [(r, ROLE_LABELS[r]) for r in roles],
        "nav_items": nav_items_for(role, request.path),
    }
