"""Admin registration for accounts app — Company + custom User."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import Company, User


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'industry', 'size_bracket', 'employee_count_estimate', 'geographic_scope', 'created_at')
    list_filter = ('industry', 'size_bracket', 'geographic_scope', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    fieldsets = (
        ('Identification', {
            'fields': ('id', 'name', 'industry'),
        }),
        ('Size & geography', {
            'fields': ('size_bracket', 'employee_count_estimate', 'geographic_scope', 'revenue_bracket'),
        }),
        ('Regulatory', {
            'fields': ('primary_regulations',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    ordering = ('name',)


class SRJUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email', 'name', 'company', 'role', 'title')


class SRJUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    add_form = SRJUserCreationForm
    form = SRJUserChangeForm
    model = User

    list_display = ('email', 'name', 'company', 'role', 'is_active', 'is_staff', 'is_superuser', 'last_login')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'company', 'role')
    search_fields = ('email', 'name', 'company__name', 'title')
    readonly_fields = ('id', 'last_login', 'created_at')
    ordering = ('email',)

    fieldsets = (
        ('Identification', {
            'fields': ('id', 'email', 'name'),
        }),
        ('Profile', {
            'fields': ('company', 'role', 'title', 'phone'),
        }),
        ('Authentication', {
            'fields': ('password',),
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Verification', {
            'fields': ('email_verified_at',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('last_login', 'last_login_at', 'created_at'),
            'classes': ('collapse',),
        }),
    )

    add_fieldsets = (
        ('Create user', {
            'classes': ('wide',),
            'fields': ('email', 'name', 'company', 'role', 'title', 'password1', 'password2'),
        }),
    )
