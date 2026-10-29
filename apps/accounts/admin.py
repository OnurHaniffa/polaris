from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import ProgramMembership, User


class UserAdminCreationForm(AdminUserCreationForm):
    """Django's form asks for a username; ours has none, so list the fields we do have."""

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")


class UserAdminChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


class MembershipInline(admin.TabularInline):
    model = ProgramMembership
    extra = 0


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    inlines = [MembershipInline]
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "student_number", "is_staff")
    search_fields = ("email", "first_name", "last_name", "student_number")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "student_number")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(ProgramMembership)
class ProgramMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "program", "role", "cohort_year")
    list_filter = ("program", "role", "cohort_year")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    autocomplete_fields = ("user",)
