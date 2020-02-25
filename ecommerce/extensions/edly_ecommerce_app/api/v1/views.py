"""
Views for API v1.
"""

from django.contrib.sites.shortcuts import get_current_site
from django.middleware import csrf

from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.extensions.edly_ecommerce_app.api.v1.constants import ERROR_MESSAGES
from ecommerce.theming.models import SiteTheme


class SiteThemesActions(APIView):
    """
    Site Theme Configurations Retrieve/Update.
    """
    authentication_classes = (SessionAuthentication,)
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Return queryset on the basis of current site.
        """
        current_site = get_current_site(request)
        current_site_theme = SiteTheme.objects.select_related('site').filter(site=current_site).values(
            'theme_dir_name',
            'site__name'
        )
        return Response(current_site_theme)

    def post(self, request):
        theme_dir_name = request.data.get('theme_dir_name', None)

        if not theme_dir_name:
            return Response(
                {'error': ERROR_MESSAGES.get('SITE_THEME_DIRECTORY_MISSING')},
                status=status.HTTP_400_BAD_REQUEST
            )

        current_site = get_current_site(request)

        try:
            SiteTheme.objects.filter(site=current_site).update(theme_dir_name=theme_dir_name)
            return Response(
                {'success': ERROR_MESSAGES.get('SITE_THEME_UPDATE_SUCCESS')},
                status=status.HTTP_200_OK
            )
        except TypeError:
            return Response(
                {'error': ERROR_MESSAGES.get('SITE_THEME_UPDATE_FAILURE')},
                status=status.HTTP_400_BAD_REQUEST
            )


class UserSessionInfo(APIView):
    """
    Get User Session Info
    """

    authentication_classes = (SessionAuthentication,)
    permission_classes = [IsAuthenticated]

    def get(self, request):
        csrf_token = csrf.get_token(request)
        data = {'csrf_token': csrf_token}
        return Response(data)
