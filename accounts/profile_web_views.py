
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError
from django.shortcuts import render, redirect

from .models import UserAccount


@login_required
def employee_profile_edit(request):
    user = request.user

    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()

        if not first_name or not last_name or not email:
            messages.error(
                request,
                "All fields are required."
            )
        else:
            try:
                validate_email(email)

                if UserAccount.objects.filter(
                    email__iexact=email
                ).exclude(pk=user.pk).exists():
                    messages.error(
                        request,
                        "This email address is already in use."
                    )
                else:
                    user.first_name = first_name
                    user.last_name = last_name
                    user.email = email
                    user.save(
                        update_fields=[
                            "first_name",
                            "last_name",
                            "email"
                        ]
                    )

                    messages.success(
                        request,
                        "Your profile was updated successfully."
                    )
                    return redirect("employee_profile_edit")

            except ValidationError:
                messages.error(
                    request,
                    "Please enter a valid email address."
                )
            except IntegrityError:
                messages.error(
                    request,
                    "Unable to update your profile."
                )

    return render(
        request,
        "accounts/employee_profile_edit.html",
        {"account": user}
    )


@login_required
def employee_change_password(request):
    if request.method == "POST":
        form = PasswordChangeForm(
            user=request.user,
            data=request.POST
        )

        if form.is_valid():
            user = form.save()

            update_session_auth_hash(
                request,
                user
            )

            messages.success(
                request,
                "Your password was changed successfully."
            )

            return redirect("employee_change_password")
    else:
        form = PasswordChangeForm(
            user=request.user
        )

    return render(
        request,
        "accounts/employee_change_password.html",
        {"form": form}
    )
