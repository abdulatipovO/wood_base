from functools import wraps
from django.http import JsonResponse
from django.contrib import messages
from django.shortcuts import redirect


def check_active_user(func):
    @wraps(func)
    def wrapper(view, request, *args, **kwargs):
        if request.user.is_staff:
            return func(view, request, *args, **kwargs)
        else:
            
            return JsonResponse({'status':400,'message':"Sizda bu amalni bajarish uchun ruxsat yo'q !"})

    return wrapper

def check_active_user_view(func):
    @wraps(func)
    def wrapper(view, request, *args, **kwargs):
        if request.user.is_staff:
            return func(view, request, *args, **kwargs)
        else:
            messages.add_message(request, messages.ERROR, "Sizda bu amalni bajarish uchun ruxsat yo'q !")
            return redirect(f'{request.path}')

    return wrapper