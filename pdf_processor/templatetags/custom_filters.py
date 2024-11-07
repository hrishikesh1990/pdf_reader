from django import template

register = template.Library()

@register.filter(name='replace')
def replace(value, arg):
    """Replace all instances of arg in the string with a space"""
    return value.replace(arg, ' ') 