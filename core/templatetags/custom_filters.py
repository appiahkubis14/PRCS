from django import template

register = template.Library()

@register.filter
def getcrumbs(path):
    """Split a URL path into segments, excluding leading/trailing slashes."""
    if not path:
        return []
    return path.strip('/').split('/')

@register.filter
def modulo(value, arg):
    """Return the modulo of value by arg."""
    try:
        return int(value) % int(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def split(value, arg):
    """Split a string by the given argument and return the last part."""
    return value.split(arg)[-1] if value else value

@register.filter
def mul(value, arg):
    """Multiply two numbers."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''


import os


@register.filter
def basename(value):
    return os.path.basename(value)


# myapp/templatetags/math_filters.py
from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    return value * arg


from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)







