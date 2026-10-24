
from django.urls import path

from . import web_views


urlpatterns = [

    # Performance Review List
    path(
        '',
        web_views.performance_review_list,
        name='performance_review_list'
    ),

    # Create Performance Review
    path(
        'create/',
        web_views.performance_review_create,
        name='performance_review_create'
    ),

]
