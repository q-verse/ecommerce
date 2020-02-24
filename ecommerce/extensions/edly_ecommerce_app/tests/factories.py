"""
Provides factories for ecommerce models.
"""
import factory
from django.contrib.sites.models import Site
from factory.django import DjangoModelFactory

from ecommerce.theming.models import SiteTheme


class SiteFactory(DjangoModelFactory):
    """
    Factory class for Site model.
    """

    class Meta(object):
        model = Site
        django_get_or_create = ('domain',)

    domain = factory.Sequence('{}.testserver.fake'.format)
    name = factory.SelfAttribute('domain')


class SiteThemeFactory(DjangoModelFactory):
    """
    Factory class for SiteTheme model
    """

    class Meta(object):
        model = SiteTheme
        django_get_or_create = ('theme_dir_name',)

    site = factory.SubFactory(SiteFactory)
    theme_dir_name = 'st-lutherx-ecommerce'
