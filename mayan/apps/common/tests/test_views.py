from __future__ import absolute_import, unicode_literals

from django.conf.urls import url
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import HttpResponse
from django.template import Context, Template
from django.test.utils import ContextList
from django.urls import clear_url_caches, reverse

from acls.models import AccessControlList
from permissions.models import Role
from permissions.tests.literals import TEST_ROLE_LABEL
from user_management.tests import (
    TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME, TEST_ADMIN_EMAIL,
    TEST_GROUP_NAME, TEST_USER_EMAIL, TEST_USER_USERNAME, TEST_USER_PASSWORD
)

from .base import BaseTestCase
from .literals import TEST_VIEW_NAME, TEST_VIEW_URL


class GenericViewTestCase(BaseTestCase):
    def setUp(self):
        super(GenericViewTestCase, self).setUp()
        self.has_test_view = False
        self.admin_user = get_user_model().objects.create_superuser(
            username=TEST_ADMIN_USERNAME, email=TEST_ADMIN_EMAIL,
            password=TEST_ADMIN_PASSWORD
        )

        self.user = get_user_model().objects.create_user(
            username=TEST_USER_USERNAME, email=TEST_USER_EMAIL,
            password=TEST_USER_PASSWORD
        )

        self.group = Group.objects.create(name=TEST_GROUP_NAME)
        self.role = Role.objects.create(label=TEST_ROLE_LABEL)
        self.group.user_set.add(self.user)
        self.role.groups.add(self.group)

    def tearDown(self):
        from mayan.urls import urlpatterns

        self.client.logout()
        if self.has_test_view:
            urlpatterns.pop(0)
        super(GenericViewTestCase, self).tearDown()

    def add_test_view(self, test_object):
        from mayan.urls import urlpatterns

        def test_view(request):
            template = Template('{{ object }}')
            context = Context(
                {'object': test_object, 'resolved_object': test_object}
            )
            return HttpResponse(template.render(context=context))

        urlpatterns.insert(0, url(TEST_VIEW_URL, test_view, name=TEST_VIEW_NAME))
        clear_url_caches()
        self.has_test_view = True

    def get_test_view(self):
        response = self.get(TEST_VIEW_NAME)
        if isinstance(response.context, ContextList):
            # template widget rendering causes test client response to be
            # ContextList rather than RequestContext. Typecast to dictionary
            # before updating.
            result = dict(response.context).copy()
            result.update({'request': response.wsgi_request})
            return Context(result)
        else:
            response.context.update({'request': response.wsgi_request})
            return Context(response.context)

    def get(self, viewname, *args, **kwargs):
        data = kwargs.pop('data', {})
        follow = kwargs.pop('follow', False)

        return self.client.get(
            reverse(viewname=viewname, *args, **kwargs),
            data=data, follow=follow
        )

    def grant_access(self, permission, obj):
        AccessControlList.objects.grant(
            permission=permission, role=self.role, obj=obj
        )

    def grant_permission(self, permission):
        self.role.permissions.add(
            permission.stored_permission
        )

    def login(self, username, password):
        logged_in = self.client.login(username=username, password=password)

        user = get_user_model().objects.get(username=username)

        self.assertTrue(logged_in)
        self.assertTrue(user.is_authenticated)

    def login_user(self):
        self.login(username=TEST_USER_USERNAME, password=TEST_USER_PASSWORD)

    def login_admin_user(self):
        self.login(username=TEST_ADMIN_USERNAME, password=TEST_ADMIN_PASSWORD)

    def logout(self):
        self.client.logout()

    def post(self, viewname, *args, **kwargs):
        data = kwargs.pop('data', {})
        follow = kwargs.pop('follow', False)

        return self.client.post(
            reverse(viewname=viewname, *args, **kwargs),
            data=data, follow=follow
        )


class CommonViewTestCase(GenericViewTestCase):
    def test_about_view(self):
        self.login(username=TEST_USER_USERNAME, password=TEST_USER_PASSWORD)

        response = self.get('common:about_view')
        self.assertContains(response, text='About', status_code=200)
