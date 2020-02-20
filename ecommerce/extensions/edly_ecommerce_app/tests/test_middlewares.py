# -*- coding: utf-8 -*-
"""
Unit tests for middlewares.
"""
from datetime import datetime, timedelta
from unittest import TestCase

import pytest
from django.contrib.auth.models import User
from django.test.client import Client
from mock import MagicMock

from edly_panel_app.middleware import EdlyUserActivityMiddleware
from edly_panel_app.models import EdlyUserActivity
from edly_panel_app.tests.factories import USER_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db


class EdlyUserActivityMiddlewareTests(TestCase):

    def setUp(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.request = MagicMock()
        self.request.user = self.user

    def test_last_acitvity_is_not_stored_in_session(self):
        """
        Check if activity date is not stored in session.

        if 'edly_user_activity_date' is not stored in the
        session then user activity should be stored and
        'edly_user_activity_date' should be updated.
        """
        self.request.session = {}
        EdlyUserActivityMiddleware().process_request(self.request)
        assert EdlyUserActivity.objects.all().count() == 1

    def test_last_activity_is_set_for_today(self):
        """
        Check if activity date is set for today.

        if 'edly_user_activity_date' is set for current date
        then no user activity should be stored.
        """
        self.request.session = {
            'edly_user_activity_date': str(datetime.now().date())
        }
        EdlyUserActivityMiddleware().process_request(self.request)
        assert EdlyUserActivity.objects.all().count() == 0

    def test_stored_activity_is_set_for_past(self):
        """
        Check if activity date is set for past.

        if 'edly_user_activity_date' is set for any past date
        then 'edly_user_activity_date' key in the session should be upated and
        current activity should be stored in the database.
        """
        past_date = (datetime.now() - timedelta(days=1)).date()
        self.request.session = {
            'edly_user_activity_date': str(past_date)
        }
        EdlyUserActivityMiddleware().process_request(self.request)
        assert EdlyUserActivity.objects.all().count() == 1
        assert self.request.session.get('edly_user_activity_date') == str(datetime.now().date())

    def test_stored_activity_is_set_for_future(self):
        """
        Check if activity date is set for future.

        if 'edly_user_activity_date' is set for any future date
        then 'edly_user_activity_date' key in the session should be upated and
        current activity should be stored in the database.
        """
        future_date = (datetime.now() + timedelta(days=1)).date()
        self.request.session = {
            'edly_user_activity_date': str(future_date)
        }
        EdlyUserActivityMiddleware().process_request(self.request)
        assert EdlyUserActivity.objects.all().count() == 1
        assert self.request.session.get('edly_user_activity_date') == str(datetime.now().date())
