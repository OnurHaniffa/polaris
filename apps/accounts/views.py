from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from apps.accounts.forms import EmailAuthenticationForm
from apps.accounts.permissions import ordered_roles
from apps.core.middleware import SESSION_KEY
from apps.core.navigation import ROLE_LABELS


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


@login_required
@require_POST
def switch_role(request):
    """Change which hat the user is wearing (B1 AC 4). Pure preference: access is unchanged."""
    role = request.POST.get("role", "")
    if role in ordered_roles(request.user):
        request.session[SESSION_KEY] = role
        messages.info(request, f"You are now viewing POlaris as: {ROLE_LABELS[role]}.")
    else:
        messages.warning(request, "You don't have that role.")
    return redirect("home")
