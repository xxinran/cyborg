# Copyright 2018 Lenovo, Inc.
# All Rights Reserved.
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
from six.moves import http_client

from oslo_serialization import jsonutils

from cyborg.api.controllers.v2.device_profiles import DeviceProfile
from cyborg import objects
from cyborg.tests.unit.api.controllers.v2 import base as v2_test
from cyborg.tests.unit import fake_device_profile


class TestDeviceProfileController(v2_test.APITestV2):

    DP_URL = '/device_profiles'

    def setUp(self):
        super(TestDeviceProfileController, self).setUp()
        self.headers = self.gen_headers(self.context)
        self.fake_dps = fake_device_profile.get_fake_device_profiles()
        assert isinstance(self.fake_dps, list)
        assert all(isinstance(dp, objects.DeviceProfile)
                   for dp in self.fake_dps)

    @mock.patch('cyborg.objects.DeviceProfile.list')
    def _test_get_one(self, mock_dp):
        dp = self.fake_dps[0]
        mock_dp.return_value = dp
        url = self.DP_URL + '/%s'
        data = self.get_json(url % dp['name'], headers=self.headers)
        for field in dp.keys():
            if field != 'profile_json':
                self.assertEqual(dp[field], data[field])
            else:
                pass
        mock_dp.assert_called_once_with(mock.ANY, dp['name'])

    def _test_get_all_initial(self):
        data = self.get_json(self.DP_URL, headers=self.headers)
        self.assertEqual(data, {u'device_profiles': []})

    def _test_create(self):
        dps = get_device_profiles()
        response = self.post_json(self.DP_URL,
                                  dps[0], headers=self.headers)
        self.assertEqual(http_client.CREATED, response.status_int)

        response = self.post_json(self.DP_URL,
                                  dps[1], headers=self.headers)
        self.assertEqual(http_client.CREATED, response.status_int)

        # Verify that both got created
        data = self.get_json(self.DP_URL, headers=self.headers)
        devprof_list = data['device_profiles']
        self.assertEqual(len(devprof_list), 2)
        self.assertEqual(devprof_list[0]['name'], 'afaas_example.1')
        self.assertEqual(devprof_list[1]['name'], 'daas_example.1')
