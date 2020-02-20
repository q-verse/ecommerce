# -*- coding: utf-8 -*-
from datetime import datetime
from unittest import TestCase

import pytest

from edly_panel_app.models import EdlyUserActivity
from edly_panel_app.tests.factories import EdlyUserActivityFactory, UserFactory

pytestmark = pytest.mark.django_db

class EdlyUserActivityModelTests(TestCase):

    def setUp(self):
        self.user = UserFactory()

    def test_string_representation(self):
        EdlyUserActivityFactory(user=self.user)
        active_user = EdlyUserActivity.objects.filter(user=self.user).first()
        expected_string = '{username} was active on {active_date}.'.format(
            username=self.user.username, active_date=datetime.now().date()
        )
        assert expected_string == str(active_user)
