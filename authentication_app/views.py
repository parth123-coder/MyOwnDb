from django.shortcuts import render,redirect
from django.contrib.auth.forms import UserCreationForm,AuthenticationForm
from django.contrib.auth import login,logout
from .middlewares import middelware,stop_login

# Create your views here.
@stop_login
def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard:home')
    else:
        form = UserCreationForm()
    return render(request, 'authentication_app/register.html', {'form': form})

@stop_login
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard:home')
    else:
        form = AuthenticationForm()
    return render(request, 'authentication_app/login.html', {'form': form})              

@middelware
def dashboard_view(request):
    return render(request,"dashboard/base.html")


def logout_view(request):
    logout(request)
    return redirect('login')

@middelware
def delete_account_view(request):
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        return redirect('login')
    return render(request, 'authentication_app/delete_account.html')
