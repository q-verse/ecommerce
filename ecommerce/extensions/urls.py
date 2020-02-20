from django.conf.urls import include, url

from ecommerce.extensions.app import application
from ecommerce.extensions.payment.app import application as payment

urlpatterns = [
    url(r'^api/', include('ecommerce.extensions.api.urls', namespace='api')),
    url(
        r'^edly_ecommerce_api/',
        include('ecommerce.extensions.edly_ecommerce_app.api.v1.urls', namespace='edly_ecommerce_api')
    ),
    url(r'^payment/', include(payment.urls)),
    url(r'', include(application.urls)),
]
