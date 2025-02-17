from django.shortcuts import render

def index(request):
    return render(request, 'app/index.html')  # We'll create this template next