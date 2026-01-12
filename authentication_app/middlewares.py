#  middleewares/decorators

from django.shortcuts import redirect

def middelware(view_function):
    def wrapped_view(request,*args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        return view_function(request,*args, **kwargs)
    return wrapped_view
def stop_login(view_function):
    def wrapped_view(request,*args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return view_function(request,*args, **kwargs)
    return wrapped_view

# this is my own web databaste built through django and plain html,css,js with sqlite3 