# Copyright 2019 Intel, Inc.
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

import json
import pecan
from six.moves import http_client
import wsme
from wsme import types as wtypes

from oslo_log import log
from oslo_serialization import jsonutils
from oslo_utils import uuidutils

from cyborg.api.controllers import base
from cyborg.api.controllers import link
from cyborg.api.controllers.v2 import types
from cyborg.api.controllers.v2 import utils as api_utils
from cyborg.api import expose
from cyborg.common import exception
from cyborg.common import policy
from cyborg import objects
from cyborg.quota import QUOTAS
from cyborg.agent.rpcapi import AgentAPI

LOG = log.getLogger(__name__)


"""
The device profile object and db table has a profile_json field, which has
its own version apart from the device profile groups field. The reasoning
behind that was this structure may evolve more rapidly. Since then the
feedback has been to manage this with the API version itself, preferably
with microversions, rather than use a second version.

One problem with that is that we have to decide on a suitable db
representation for device profile groups, which form an array of
string pairs. The Cyborg community wishes to keep the number of
tables small and manageable.

TODO(Sundar): As of now, the db and objects layer for device profiles
still use the profile_json field. But the API layer returns the device
profile as it should be. The objects layer does the conversion.
"""


class DeviceProfile(base.APIBase):
    """API representation of a device profile.

    This class enforces type checking and value constraints, and converts
    between the internal object model and the API representation of
    a device profile. See module notes above.
    """

    @classmethod
    def get_api_obj(cls, obj_devprof):
        groups = obj_devprof['groups']
        api_obj = {}
        # TODO add description field in db, objects and here
        for field in ['name', 'uuid', 'groups']:
            api_obj[field] = obj_devprof[field]
        api_obj['links'] = [
            link.Link.make_link_dict('device_profiles', api_obj['name'])
            ]
        return api_obj


class DeviceProfileCollection(object):
    """API representation of a collection of device profiles."""

    @classmethod
    def get_api_objs(cls, obj_devprofs):
        api_obj_devprofs = [
            DeviceProfile.get_api_obj(obj_devprof)
            for obj_devprof in obj_devprofs]
        return api_obj_devprofs


class DeviceProfilesController(base.CyborgController):
    """REST controller for Device Profiles."""

    # TODO Add RBAC for device profiles and all objects
    # @policy.authorize_wsgi("cyborg:device_profile", "create", False)
    @expose.expose('json', body=types.jsontype,
                   status_code=http_client.CREATED)
    def post(self, req_devprof):
        """Create a new device_profile.

        :param devprof: a device_profile within the request body.
         { "name": <string>,
           "groups": [ {"key1: "value1", "key2": "value2"} ]
           "uuid": <uuid> # optional
         }
        """
        # TODO Support more than one devprof per request
        # TODO validate that device profile names look like (\w)+

        context = pecan.request.context
        obj_devprof = objects.DeviceProfile(context, **req_devprof)

        # TODO Only the conductor must write to the db
        obj_devprof.create(context)
        ret = DeviceProfile.get_api_obj(obj_devprof)
        return wsme.api.Response(ret, status_code=http_client.CREATED,
                                 return_type=wsme.types.DictType)

    def _get_device_profile_list(self, names):
        """Get a list of API objects representing device profiles."""

        assert isinstance(names, list)

        context = pecan.request.context
        obj_devprofs = objects.DeviceProfile.list(context)
        if names != []:
            new_obj_devprofs = [devprof for devprof in obj_devprofs
                                if devprof['name'] in names]
            obj_devprofs = new_obj_devprofs

        api_obj_devprofs = DeviceProfileCollection.get_api_objs(obj_devprofs)

        assert isinstance(api_obj_devprofs, list)
        return api_obj_devprofs

    # @policy.authorize_wsgi("cyborg:device_profile", "get_all")
    @expose.expose('json', wtypes.text)
    def get_all(self, name=None):
        """Retrieve a list of device profiles."""
        names = pecan.request.GET.get('name')
        if names is not None:
            names = names.split(',')
        else:
            names = []
        LOG.info('[device_profiles] get_all. names=%s', names)
        api_obj_devprofs = self._get_device_profile_list(names)

        ret = {"device_profiles": api_obj_devprofs}
        LOG.info('[device_profiles] get_all returned: %s', ret)
        return wsme.api.Response(ret, status_code=http_client.OK,
                                 return_type=wsme.types.DictType)

    # @policy.authorize_wsgi("cyborg:device_profile", "get_one")
    @expose.expose('json', wtypes.text)
    def get_one(self, name):
        """Retrieve a single device profile by name."""
        names = [name]
        api_obj_devprofs = self._get_device_profile_list(names)
        if len(api_obj_devprofs) == 0:
            raise exception.DeviceProfileNameNotFound(name=name)

        assert len(api_obj_devprofs) == 1
        ret = {"device_profiles": api_obj_devprofs[0]}
        return wsme.api.Response(ret, status_code=http_client.OK,
                                 return_type=wsme.types.DictType)

    # @policy.authorize_wsgi("cyborg:device_profile", "delete")
    @expose.expose(None, wtypes.text, status_code=http_client.NO_CONTENT)
    def delete(self, name):
        """Delete a device_profile.

        :param name: name of a device_profile.
        TODO Support more than one devprof per request
        """
        context = pecan.request.context
        obj_devprof = objects.DeviceProfile.get(context, name)
        # TODO Implement device profile delete via conductor
        obj_devprof.destroy(context)
