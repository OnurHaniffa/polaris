from __future__ import annotations

from django.urls import NoReverseMatch, reverse

ROLE_LABELS = {
    "head": "Department head",
    "instructor": "Instructor",
    "student": "Student",
    "admin": "Admin",
}

# (label, url name) per active role, in navbar order
NAV = {
    "student": [("My profile", "student:profile")],
    "instructor": [("My courses", "catalog:teaching")],
    "head": [
        ("Overview", "reports:department"),
        ("Offerings", "catalog:offerings"),
        ("Terms", "catalog:terms"),
        ("Courses", "catalog:courses"),
        ("Outcomes", "catalog:outcomes"),
        ("My courses", "catalog:teaching"),
    ],
    "admin": [("Offerings", "catalog:offerings"), ("Django admin", "admin:index")],
}

# Each tab: (label, url name). Tabs whose view doesn't exist yet are hidden.
OFFERING_TABS = [
    ("Overview", "catalog:offering"),
    ("Setup", "outcomes:setup"),
    ("Mapping", "outcomes:mapping"),
    ("Grades", "grading:sheet"),
    ("Results", "reports:results"),
    ("History", "reports:history"),
]


def safe_reverse(name: str, **kwargs) -> str | None:
    try:
        return reverse(name, kwargs=kwargs or None)
    except NoReverseMatch:
        return None


def nav_items_for(role: str | None, current_path: str) -> list[dict]:
    items = []
    for label, name in NAV.get(role or "", []):
        url = safe_reverse(name)
        if url:
            items.append({"label": label, "url": url, "active": current_path.startswith(url)})
    return items


def offering_tabs(offering, current: str) -> list[dict]:
    """Tabs for the offering pages. `current` is the url name of the page being shown."""
    tabs = []
    for label, name in OFFERING_TABS:
        url = safe_reverse(name, offering_id=offering.pk)
        if url:
            tabs.append({"label": label, "url": url, "active": name == current})
    return tabs
