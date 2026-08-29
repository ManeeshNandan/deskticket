from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Q
from django.utils.text import slugify

from .models import (
    Ticket, TicketComment, TicketAttachment, EmailAccount, Organization,
    Department, Category, Customer, Membership, SLAPolicy,
)
from .services.security import encrypt

User = get_user_model()


class StyledFormMixin:
    """Apply consistent Bootstrap controls across every DeskTicket form."""

    def _style_fields(self):
        for name, field in self.fields.items():
            widget = field.widget
            existing = widget.attrs.get("class", "")

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = f"form-check-input {existing}".strip()
            elif isinstance(widget, forms.FileInput):
                widget.attrs["class"] = f"form-control {existing}".strip()
            elif isinstance(widget, forms.Select):
                widget.attrs["class"] = f"form-select {existing}".strip()
            else:
                widget.attrs["class"] = f"form-control {existing}".strip()

            if field.required:
                widget.attrs["required"] = True


class SignupForm(StyledFormMixin, UserCreationForm):
    first_name = forms.CharField(max_length=150, label="First name")
    last_name = forms.CharField(max_length=150, required=False, label="Last name")
    email = forms.EmailField(label="Email address")
    organization = forms.CharField(max_length=150, label="Workspace name")

    class Meta:
        model = User
        fields = (
            "first_name", "last_name", "email", "username",
            "organization", "password1", "password2",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
        self.fields["username"].help_text = "Use a simple username for signing in."
        self.fields["organization"].help_text = "This becomes your DeskTicket workspace name."
        self.fields["password1"].help_text = "Use at least 8 characters."

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(
                "Username is unavailable. Please choose another username."
            )
        return username

    def clean_organization(self):
        name = " ".join(self.cleaned_data["organization"].split())
        slug = slugify(name)
        if not slug:
            raise forms.ValidationError(
                "Please enter a valid workspace name."
            )
        if Organization.objects.filter(slug=slug).exists():
            raise forms.ValidationError(
                "Workspace name is unavailable. Please choose a different name."
            )
        return name


class TicketForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Ticket
        fields = [
            "subject", "description", "requester_name", "requester_email",
            "priority", "department", "category", "assigned_to",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 8}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["department"].queryset = Department.objects.filter(
                organization=organization, is_active=True
            ).order_by("name")
            self.fields["category"].queryset = Category.objects.filter(
                organization=organization, is_active=True
            ).select_related("department").order_by("department__name", "name")
            self.fields["assigned_to"].queryset = User.objects.filter(
                memberships__organization=organization,
                memberships__is_active=True,
                memberships__role__in=["OWNER", "ADMIN", "MANAGER", "AGENT"],
            ).distinct().order_by("first_name", "username")
        self._style_fields()


class CustomerTicketForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["subject", "description", "priority", "department", "category"]
        widgets = {"description": forms.Textarea(attrs={"rows": 8})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["department"].queryset = Department.objects.filter(
                organization=organization, is_active=True
            ).order_by("name")
            self.fields["category"].queryset = Category.objects.filter(
                organization=organization, is_active=True
            ).select_related("department").order_by("department__name", "name")
        self._style_fields()


class TicketUpdateForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["status", "priority", "department", "category", "assigned_to", "sla_policy"]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["department"].queryset = Department.objects.filter(
                organization=organization, is_active=True
            ).order_by("name")
            self.fields["category"].queryset = Category.objects.filter(
                organization=organization, is_active=True
            ).select_related("department").order_by("department__name", "name")
            self.fields["assigned_to"].queryset = User.objects.filter(
                memberships__organization=organization,
                memberships__is_active=True,
                memberships__role__in=["OWNER", "ADMIN", "MANAGER", "AGENT"],
            ).distinct().order_by("first_name", "username")
            self.fields["sla_policy"].queryset = SLAPolicy.objects.filter(
                organization=organization, is_active=True
            ).order_by("priority", "name")
        self._style_fields()


class CommentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TicketComment
        fields = ["comment", "is_internal"]
        widgets = {
            "comment": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "Write an internal note...",
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class ReplyForm(StyledFormMixin, forms.Form):
    body = forms.CharField(
        label="Message",
        widget=forms.Textarea(attrs={
            "rows": 6,
            "placeholder": "Write your reply...",
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class AttachmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TicketAttachment
        fields = ["file"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class EmailAccountForm(StyledFormMixin, forms.ModelForm):
    secret = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        label="Password / App Password",
        help_text="Leave blank when editing to keep the saved secret.",
    )
    oauth_client_id = forms.CharField(required=False, label="OAuth Client ID")
    oauth_client_secret = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        label="OAuth Client Secret",
    )
    oauth_refresh_token = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        label="OAuth Refresh Token",
    )

    class Meta:
        model = EmailAccount
        exclude = [
            "organization", "secret_encrypted", "oauth_refresh_token_encrypted",
            "oauth_client_id_encrypted", "oauth_client_secret_encrypted",
            "last_uid", "last_checked_at", "last_error",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
        self.fields["email"].widget.attrs["placeholder"] = "support@company.com"
        self.fields["username"].widget.attrs["placeholder"] = "Usually the mailbox email"

    def save(self, commit=True):
        obj = super().save(commit=False)
        secret = self.cleaned_data.get("secret")
        if secret:
            obj.secret_encrypted = encrypt(secret)
        for field, attr in [
            ("oauth_client_id", "oauth_client_id_encrypted"),
            ("oauth_client_secret", "oauth_client_secret_encrypted"),
            ("oauth_refresh_token", "oauth_refresh_token_encrypted"),
        ]:
            value = self.cleaned_data.get(field)
            if value:
                setattr(obj, attr, encrypt(value))
        if commit:
            obj.save()
        return obj


class DepartmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "code", "is_active"]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self._style_fields()

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()
        if self.organization and Department.objects.filter(
            organization=self.organization,
            code__iexact=code,
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(
                "Department code is already in use in this workspace."
            )
        return code


class CategoryForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["department", "name", "is_active"]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        if organization:
            self.fields["department"].queryset = Department.objects.filter(
                organization=organization, is_active=True
            ).order_by("name")
        self._style_fields()

    def clean(self):
        cleaned = super().clean()
        department = cleaned.get("department")
        name = (cleaned.get("name") or "").strip()
        if department and self.organization and department.organization_id != self.organization.id:
            self.add_error("department", "Select a department from this workspace.")
        if department and name:
            exists = Category.objects.filter(
                department=department, name__iexact=name
            ).exclude(pk=self.instance.pk).exists()
            if exists:
                self.add_error(
                    "name",
                    "A category with this name already exists in this department.",
                )
        cleaned["name"] = name
        return cleaned


class SLAForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SLAPolicy
        fields = [
            "name", "priority", "first_response_minutes",
            "resolution_minutes", "warning_percent", "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class CustomerForm(StyledFormMixin, forms.Form):
    name = forms.CharField(max_length=150, label="Full name")
    email = forms.EmailField(label="Email address")
    phone = forms.CharField(max_length=50, required=False)
    company = forms.CharField(max_length=150, required=False)
    notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}), required=False
    )
    username = forms.CharField(
        max_length=150,
        required=False,
        help_text="Leave blank to generate a portal username automatically.",
    )
    password = forms.CharField(
        widget=forms.PasswordInput,
        min_length=8,
        label="Portal password",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class MemberForm(StyledFormMixin, forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150, required=False)
    role = forms.ChoiceField(choices=Membership.Role.choices)
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
