
from django.urls import path

from .web_views import (
    user_account_list,
    user_account_create,
    user_account_edit,
    user_account_activate,
)

from .profile_web_views import (
    employee_profile_edit,
    employee_change_password,
)


urlpatterns = [

    # =====================================================
    # USER ACCOUNT MANAGEMENT - HR OFFICER
    # =====================================================

    # View All User Accounts
    path(
        '',
        user_account_list,
        name='user_account_list'
    ),

    # Create User Account
    path(
        'create/',
        user_account_create,
        name='user_account_create'
    ),

    # Edit User Account
    path(
        '<int:user_id>/edit/',
        user_account_edit,
        name='user_account_edit'
    ),

    # =====================================================
    # ACCOUNT ACTIVATION
    # =====================================================

    # Password Setup and Account Activation
    path(
        'activate/<uidb64>/<token>/',
        user_account_activate,
        name='user_account_activate'
    ),

    # =====================================================
    # EMPLOYEE SELF-SERVICE
    # =====================================================

    # Employee - Edit Own Profile
    path(
        'my-profile/',
        employee_profile_edit,
        name='employee_profile_edit'
    ),

    # Employee - Change Own Password
    path(
        'change-password/',
        employee_change_password,
        name='employee_change_password'
    ),

]
