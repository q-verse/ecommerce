from django.conf.urls import url

from ecommerce.extensions.edly_ecommerce_app.api.v1 import views


app_name = 'v1'
urlpatterns = [
    url(r'site_themes/', views.SiteThemesActions.as_view(), name='site_themes'),
]
