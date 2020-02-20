from django.conf.urls import include, url

app_name = 'edly_ecommerce_app'

urlpatterns = [
    url(r'^v1/', include('edly_ecommerce_app.api.v1.urls')),
]
