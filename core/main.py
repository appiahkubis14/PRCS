from django.shortcuts import render
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods


User = get_user_model()

@login_required
def index(request):
    return render(request, 'core/pages/index.html')


def landing(request):
    return render(request, 'core/pages/landing.html')

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

@login_required
def custom_logout(request):
    logout(request)
    return redirect('landing')  # Redirect to login page after logout



@require_http_methods(["GET", "POST"])
def change_password(request):
    if request.method == 'POST':
        print(request.POST)
        form = PasswordChangeForm(request.user, request.POST)

        username = request.POST.get('username')
        current_password = request.POST.get('current_password')
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')

        if not username or not current_password or not new_password1 or not new_password2:
            messages.error(request, 'Please fill in all required fields.', extra_tags='password')
            return redirect('login')
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(request, 'User does not exist.', extra_tags='password')
            return redirect('login')
        
        if not user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.', extra_tags='password')
            return redirect('login')
        
        if new_password1 != new_password2:
            messages.error(request, 'New passwords do not match.', extra_tags='password')
            return redirect('login')
        
        # if len(new_password1) < 8:
        #     messages.error(request, 'New password must be at least 8 characters long.', extra_tags='password')
        #     return redirect('login')
        
        # Additional password validations can be added here

        user.set_password(new_password1)
        user.save()
        update_session_auth_hash(request, user)  # Important, to keep the user logged in after password change
        messages.success(request, 'Your password was successfully updated!', extra_tags='password')
        return redirect('login')
    
    # If GET request, just redirect to login page
    return redirect('login')





from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from utils import sidebar

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Permission
from django.shortcuts import render
from datetime import datetime

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import datetime

@login_required
def dashboard_view(request):
    user = request.user
    current_hour = datetime.now().hour
    current_date = timezone.now()
    
    # Get staff information if available
    staff_info = None
    position = "-"
    
    try:
        # Check if user has a related staff record
        if hasattr(user, 'staff_user'):
            staff_info = user.staff_user.first()
            if staff_info:
                position = staff_info.designation.name if staff_info.designation else "-"
    except Exception as e:
        print(f"Error fetching staff info: {e}")
        # Fail gracefully if there's an error
    
    # Get user's permissions
    permissions = user.get_all_permissions()
    
    # Process permissions for display
    processed_permissions = []
    for perm in permissions:
        # Extract the permission name (last part after dot)
        perm_name = perm.split('.')[-1]
        # Convert to human readable format
        human_readable = perm_name.replace('_', ' ').title()
        processed_permissions.append(human_readable)
    
    # Sort permissions alphabetically
    processed_permissions.sort()
    
    context = {
        "staff_info": staff_info,
        "position": position,
        "permissions": processed_permissions,
        "current_hour": current_hour,
        "current_date": current_date,
        "user": user,
    }
    return render(request, "core/pages/dashboard-index.html", context)
