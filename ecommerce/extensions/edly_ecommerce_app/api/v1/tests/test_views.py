"""
Unit tests for API v1 views.
"""
from unittest import TestCase

import pytest
import json
from django.conf import settings
from django.test.client import Client
from django.urls import reverse
from rest_framework import status

from edly_ecommerce_app.api.v1.constants import ERROR_MESSAGES

from edly_panel_app.tests.factories import (
    USER_PASSWORD,
    EdlyUserActivityFactory,
    GroupFactory,
    UserFactory,
    SiteThemeFactory
)


pytestmark = pytest.mark.django_db


class SiteThemesActionsView(TestCase):
    """
    Unit tests for site themes configurations.
    """

    def setUp(self):
        """
        Prepare environment for tests.
        """
        self.site_theme = SiteThemeFactory()
        self.edlypanel_user = UserFactory()
        self.client = Client()
        self.client.login(username=self.edlypanel_user.username, password=USER_PASSWORD)
        self.site_themes_url = reverse('edly_panel_app:v1:site_themes')

    def test_without_authentication(self):
        """
        Verify authentication is required when accessing the endpoint.
        """
        self.client.logout()
        response = self.client.get(self.site_themes_url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_current_site_theme_info(self):
        """
        Verify response on list view.
        """
        response = self.client.get(self.site_themes_url, SERVER_NAME=self.site_theme.site.domain, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()[0]['site__name'] == self.site_theme.site.domain

    def test_update_current_site_theme(self):
        """
        Test that edly users can update site theme.
        """
        edly_theme_data = {
            'theme_dir_name': "new-theme-name"
        }
        response = self.client.post(
            self.site_themes_url,
            SERVER_NAME = self.site_theme.site.domain,
            data=json.dumps(edly_theme_data),
            content_type='application/json'
        )
        assert response.status_code == status.HTTP_200_OK

        response = self.client.get(self.site_themes_url, SERVER_NAME=self.site_theme.site.domain, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()[0]['theme_dir_name'] == edly_theme_data['theme_dir_name']
