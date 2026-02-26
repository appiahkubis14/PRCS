from django.contrib.auth.decorators import login_required
from utils import sidebar

def user_has_all_permissions(user, permissions):
    return all(user.has_perm(perm) for perm in permissions)

def user_has_any_group(user_group_names, allowed_groups):
    return bool(user_group_names & set(allowed_groups))

def filter_sidebar_level(items, user_group_names, user):
    filtered_items = {}

    for item_name, item_data in items.items():
        allowed_groups = item_data.get("groups", [])
        required_permissions = item_data.get("permissions", [])
        
        # Check if user has required groups AND permissions
        has_group = not allowed_groups or user_has_any_group(user_group_names, allowed_groups)
        has_perm = not required_permissions or user_has_all_permissions(user, required_permissions)
        
        # Only proceed if user has both required groups AND permissions
        if not (has_group and has_perm):
            continue  # Skip this item completely
        
        # Recursively filter nested sub-items if any
        sub_items = item_data.get("sub_items", {})
        filtered_sub_items = filter_sidebar_level(sub_items, user_group_names, user) if sub_items else {}

        # Create the item dictionary
        item_dict = {
            "icon": item_data.get("icon"),
        }
        
        if "url" in item_data:
            item_dict["url"] = item_data["url"]
        
        # Only include sub_items if they are not empty
        if filtered_sub_items:
            item_dict["sub_items"] = filtered_sub_items
        
        # Only add the item to filtered_items if it has content (url or valid sub_items)
        if "url" in item_dict or filtered_sub_items:
            filtered_items[item_name] = item_dict
        # print(filtered_items)

    return filtered_items

def sidebar_context(request):
    if not request.user.is_authenticated:
        return {}

    user_groups = request.user.groups.all()
    user_group_names = set(user_groups.values_list('name', flat=True))

    filtered_sidebar_items = filter_sidebar_level(
        sidebar.Sidebar.sidebar_items,
        user_group_names,
        request.user
    )

    model_permissions = {}
    code_names = []

    for perm in request.user.get_all_permissions():
        try:
            app_label, codename = perm.split(".")
            code_names.append(codename)
            action, model = codename.split("_", 1)
            model_permissions.setdefault(model, []).append(action)
        except ValueError:
            continue

    return {
        "sidebar_items": filtered_sidebar_items,
        "path": request.path,
        "model_permissions": model_permissions,
        "current_user": request.user
    }