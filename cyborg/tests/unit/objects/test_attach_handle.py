# Copyright 2019 Intel, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


import mock

from cyborg import objects
from cyborg.tests.unit.db import base
from cyborg.tests.unit.db import utils


class TestAttachHandleObject(base.DbTestCase):

    def setUp(self):
        super(TestAttachHandleObject, self).setUp()
        self.fake_attach_handle = utils.get_test_attach_handle()

    def test_get(self):
        uuid = self.fake_attach_handle['uuid']
        with mock.patch.object(self.dbapi, 'attach_handle_get_by_uuid',
                               autospec=True) as mock_attach_handle_get:
            mock_attach_handle_get.return_value = self.fake_attach_handle
            attach_handle = objects.AttachHandle.get(self.context, uuid)
            mock_attach_handle_get.assert_called_once_with(self.context, uuid)
            self.assertEqual(self.context, attach_handle._context)

    def test_get_by_id(self):
        id = self.fake_attach_handle['id']
        with mock.patch.object(self.dbapi, 'attach_handle_get_by_id',
                               autospec=True) as mock_attach_handle_get:
            mock_attach_handle_get.return_value = self.fake_attach_handle
            attach_handle = objects.AttachHandle.get_by_id(self.context, id)
            mock_attach_handle_get.assert_called_once_with(self.context, id)
            self.assertEqual(self.context, attach_handle._context)

    def test_list(self):
        with mock.patch.object(self.dbapi, 'attach_handle_list',
                               autospec=True) as mock_attach_handle_list:
            mock_attach_handle_list.return_value = [self.fake_attach_handle]
            attach_handles = objects.AttachHandle.list(self.context)
            self.assertEqual(1, mock_attach_handle_list.call_count)
            self.assertEqual(1, len(attach_handles))
            self.assertIsInstance(attach_handles[0], objects.AttachHandle)
            self.assertEqual(self.context, attach_handles[0]._context)

    def test_create(self):
        with mock.patch.object(self.dbapi, 'attach_handle_create',
                               autospec=True) as mock_attach_handle_create:
            mock_attach_handle_create.return_value = self.fake_attach_handle
            attach_handle = objects.AttachHandle(self.context,
                                                 **self.fake_attach_handle)
            attach_handle.create(self.context)
            mock_attach_handle_create.assert_called_once_with(
                self.context, self.fake_attach_handle)
            self.assertEqual(self.context, attach_handle._context)

    def test_destroy(self):
        uuid = self.fake_attach_handle['uuid']
        with mock.patch.object(self.dbapi, 'attach_handle_get_by_uuid',
                               autospec=True) as mock_attach_handle_get:
            mock_attach_handle_get.return_value = self.fake_attach_handle
            with mock.patch.object(self.dbapi, 'attach_handle_delete',
                                   autospec=True) as mock_attach_handle_delete:
                attach_handle = objects.AttachHandle.get(self.context, uuid)
                attach_handle.destroy(self.context)
                mock_attach_handle_delete.assert_called_once_with(self.context,
                                                                  uuid)
                self.assertEqual(self.context, attach_handle._context)

    def test_update(self):
        uuid = self.fake_attach_handle['uuid']
        with mock.patch.object(self.dbapi, 'attach_handle_get_by_uuid',
                               autospec=True) as mock_attach_handle_get:
            mock_attach_handle_get.return_value = self.fake_attach_handle
            with mock.patch.object(self.dbapi, 'attach_handle_update',
                                   autospec=True) as mock_attach_handle_update:
                fake = self.fake_attach_handle
                fake["attach_info"] = "new_attach_info"
                mock_attach_handle_update.return_value = fake
                attach_handle = objects.AttachHandle.get(self.context, uuid)
                attach_handle.attach_info = 'new_attach_info'
                attach_handle.save(self.context)
                mock_attach_handle_get.assert_called_once_with(self.context,
                                                               uuid)
                mock_attach_handle_update.assert_called_once_with(
                    self.context, uuid,
                    {'attach_info': 'new_attach_info'})
                self.assertEqual(self.context, attach_handle._context)
