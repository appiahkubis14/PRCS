from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # path('', views.notice_board, name='home'),
  
    path('bopeasycollectible/', views.bop_easy_collectible_list, name='bopeasycollectible'),



]