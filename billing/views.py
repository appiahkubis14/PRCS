from django.shortcuts import render
from billing.models import *

# Create your views here.
def bop_easy_collectible_list(request):
    bop_easy_collectibles = BopEasyCollectible.objects.all()[:10]

    return render(request, 'billing/blue.html', locals())