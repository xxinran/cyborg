# Copyright 2018 Huawei Technologies Co.,LTD.
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

import datetime

from oslo_serialization import jsonutils

from cyborg import objects
from cyborg.objects import fields


def get_device_profile_dict():
    dp1 = {
        "id": "1",
        "uuid": "a95e10ae-b3e3-4eab-a513-1afae6f17c51",
        "name": "afaas_example_1",
        "profile_json": {
            "version": "1.0",
            "groups": [
                {"resources:CUSTOM_ACCELERATOR_FPGA": "1",
                 "trait:CUSTOM_FPGA_INTEL_PAC_ARRIA10": "required",
                 "trait:CUSTOM_FUNCTION_ID_3AFB": "required",
                 }
            ]
        }
    }
    dp2 = {
        "id": "2",
        "uuid": "199c46b7-63a7-431b-aa40-35da4b9420b1",
        "name": "daas_example_1",
        "profile_json": {
            "version": "1.0",
            "groups": [
                {"resources:CUSTOM_ACCELERATOR_FPGA": "1",
                 "trait:CUSTOM_REGION_ID_3ACD": "required",
                 "accel:bitstream_id": "ea0d149c-8555-495b-bc79-608d7bab1260"
                 }
            ]
        }
    }
    return [dp1, dp2]


def get_fake_device_profiles():
    dp_list = get_device_profile_dict()
    obj_devprofs = []
    for dp_dict in dp_list:
        obj_devprof = objects.DeviceProfile()
        for field in dp_dict.keys():  # obj_devprof.fields:
            if field == 'profile_json':
                obj_devprof[field] = jsonutils.dumps(dp_dict[field])
            else:
                obj_devprof[field] = dp_dict[field]
        obj_devprofs.append(obj_devprof)
    return obj_devprofs
