"""
Provides factories for edly_panel models.
"""
import factory
from django.contrib.auth.models import User, Group
from factory.django import DjangoModelFactory

from edly_panel_app.models import EdlyUserActivity
from student.models import UserProfile
from django.contrib.sites.models import Site
from openedx.core.djangoapps.theming.models import SiteTheme

USER_PASSWORD = 'TEST_PASSOWRD'


class UserFactory(DjangoModelFactory):
    """
    Crete user with the given credentials.
    """
    class Meta(object):
        model = User
        django_get_or_create = ('email', 'username')

    username = factory.Sequence(u'robot{0}'.format)
    email = factory.LazyAttribute(lambda obj: '%s@example.com' % obj.username)
    password = factory.PostGenerationMethodCall('set_password', USER_PASSWORD)
    is_staff = False
    is_active = True
    is_superuser = False

    @factory.post_generation
    def profile(obj, create, extracted, **kwargs):  # pylint: disable=unused-argument, no-self-argument
        if create:
            obj.save()
            return UserProfileFactory.create(user=obj, **kwargs)
        elif kwargs:
            raise Exception('Cannot build a user profile without saving the user')
        else:
            return None


class EdlyUserActivityFactory(DjangoModelFactory):
    """
    Create user activity for the given user.
    """
    class Meta(object):
        model = EdlyUserActivity

    user = factory.SubFactory(UserFactory)


class GroupFactory(DjangoModelFactory):
    """
    Create django user group.
    """
    class Meta:
        model = Group

    name = factory.Sequence(lambda n: "group_{0}".format(n))


class UserProfileFactory(DjangoModelFactory):
    class Meta(object):
        model = UserProfile
        django_get_or_create = ('user', )

    user = None
    name = factory.LazyAttribute(u'{0.user.first_name} {0.user.last_name}'.format)
    year_of_birth = None


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
    Factory class for SiteTheme model.
    """

    class Meta(object):
        model = SiteTheme
        django_get_or_create = ('theme_dir_name', )

    site = factory.SubFactory(SiteFactory)
    theme_dir_name = 'st-lutherx'
