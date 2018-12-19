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


class ARQ(base.APIBase):
    """API representation of an ARQ.

    This class enforces type checking and value constraints, and converts
    between the internal object model and the API representation.
    """
    uuid = types.uuid
    """The UUID of the device profile"""

    state = wtypes.text  # obvious meanings
    device_profile_name = wtypes.text
    device_profile_group_id = wtypes.IntegerType()

    hostname = wtypes.text
    """The host name to which the ARQ is bound, if any"""

    device_rp_uuid = wtypes.text
    """The UUID of the bound device RP, if any"""

    instance_uuid = wtypes.text
    """The UUID of the instance associated with this ARQ, if any"""

    # TODO This must be an attach_handle object
    attach_handle_type = wtypes.text
    attach_handle_info = wtypes.text

    links = wsme.wsattr([link.Link], readonly=True)
    """A list containing a self link"""

    def __init__(self, **kwargs):
        super(ARQ, self).__init__(**kwargs)
        self.fields = []
        for field in objects.ARQ.fields:
            self.fields.append(field)
            setattr(self, field, kwargs.get(field, wtypes.Unset))

    @classmethod  # TODO fix name
    def convert_with_links(cls, obj_arq):
        api_arq = cls(**obj_arq.as_dict())
        api_arq.links = [
            link.Link.make_link('self', pecan.request.public_url,
                                'accelerator_requests', api_arq.uuid)
            ]
        return api_arq


class ARQCollection(base.APIBase):
    """API representation of a collection of arqs."""

    arqs = [ARQ]
    """A list containing arq objects"""

    @classmethod
    def convert_with_links(cls, obj_arqs):
        collection = cls()
        collection.arqs = [ARQ.convert_with_links(obj_arq)
                           for obj_arq in obj_arqs]
        return collection


class ARQsController(base.CyborgController):
    """REST controller for ARQs."""

    def _get_devprof_id(self, context, devprof_name):
        """ Get the contents of a device profile.
            Since this is just a read, it is ok for the API layer
            to do this, instead of the conductor.
        """
        try:
            obj_devprof = objects.DeviceProfile.get(context, devprof_name)
            return obj_devprof['id']
        except:
            return None

    # @policy.authorize_wsgi("cyborg:arq", "create", False)
    @expose.expose(ARQCollection, body=types.jsontype,
                   status_code=http_client.CREATED)
    def post(self, req):
        """Create a new arq.
           Request body:
              { 'device_profile_name': <string>, # required
                'device_profile_group_id': <integer>, # opt, default=0
                'image_uuid': <glance-image-UUID>, #optional
              }
           :param req: request body.
        """
        # TODO assume only one ARQ per dev prof for now
        # TODO ignore image_uuid for now
        # Get devprof details and set devprof ID in arq.
        # This allows the conductor and db layer to skip the devprof query.
        context = pecan.request.context
        devprof_id = None
        if req.get('device_profile_name'):
            devprof_id = self._get_devprof_id(
                context, req['device_profile_name'])
            if devprof_id is None:
                raise exception.DeviceProfileNameNotFound(
                    name=req['device_profile_name'])
        else:
            raise exception.DeviceProfileNameNeeded()
        LOG.info('[arqs] post. device profile name=%s',
                 req['device_profile_name'])

        if not req.get('device_profile_group_id'):
            req['device_profile_group_id'] = 0

        obj_arq = objects.ARQ(context, **req)
        req['arq'] = obj_arq
        obj_extarq = objects.ExtARQ(context, **req)

        # TODO The conductor must do all db writes
        new_extarq = obj_extarq.create(context, devprof_id)

        ret = ARQCollection.convert_with_links([new_extarq.arq])
        LOG.info('[arqs] post returning: %s', ret)
        return ret

    # @policy.authorize_wsgi("cyborg:arq", "get_one")
    @expose.expose(ARQ, wtypes.text)
    def get_one(self, uuid):
        """Get a single ARQ by UUID."""
        context = pecan.request.context
        extarq = objects.ExtARQ.get(context, uuid)
        return ARQ.convert_with_links(extarq.arq)

    # @policy.authorize_wsgi("cyborg:arq", "get_all")
    @expose.expose(ARQCollection, wtypes.text, types.uuid)
    def get_all(self, bind_state=None, instance=None):
        """Retrieve a list of arqs."""
        # FIXME Translate attach handle to Python dict
        # TODO Need to implement 'arq=uuid1,...' query parameter
        LOG.info('[arqs] get_all. bind_state:(%s), instance:(%s)',
                 bind_state or '', instance or '')
        context = pecan.request.context
        extarqs = objects.ExtARQ.list(context)
        arqs = [extarq.arq for extarq in extarqs]
        # TODO (Sundar): Optimize by doing the filtering in the db layer
        # Apply instance filter before state filter.
        if instance is not None:
            new_arqs = [arq for arq in arqs
                        if arq['instance_uuid'] == instance]
            arqs = new_arqs
        if bind_state is not None:
            if bind_state != 'resolved':
                raise exception.ARQInvalidState(state=bind_state)
            unbound_flag = False
            for arq in arqs:
                if (arq['state'] != 'Bound' and
                        arq['state'] != 'BindFailed'):
                    unbound_flag = True
            if instance is not None and unbound_flag:
                # Return HTTP code 'Locked'
                # FIXME This should return HTTP code 423 if any ARQ for
                #   this instance is not resolved. But that's not
                #   working yet. For now, we compensate in cyborgclient.
                LOG.warning('HTTP Response should be 423')
                pecan.response.status = http_client.LOCKED
                return None

        ret = ARQCollection.convert_with_links(arqs)
        LOG.info('[arqs:get_all] Returning: %s', ret)
        return ret

    # @policy.authorize_wsgi("cyborg:arq", "delete")
    @expose.expose(ARQ, wtypes.text, status_code=http_client.NO_CONTENT)
    def delete(self, arqs=None):
        """Delete a arq.

        :param arq: List of ARQ UUIDs
        """
        if arqs is not None:
            arqlist = arqs.split(',')
        else:
            raise exception.NeedAtleastOne(object='ARQ UUID')

        context = pecan.request.context

        for uuid in arqlist:
            obj_extarq = objects.ExtARQ.get(context, uuid)
            # TODO Defer deletion to conductor
            obj_extarq.destroy(context)

    def _validate_arq_patch(self, patch):
        """Validate a single patch for an ARQ.

        :param patch: a JSON PATCH document.
            The patch must be of the form [{..}], as specified in the
            value field of arq_uuid in patch() method below.
        :returns: dict of valid fields
        """
        valid_fields = {'hostname': None,
                        'device_rp_uuid': None,
                        'instance_uuid': None}
        if ((not all(p['op'] == 'add' for p in patch)) and
           (not all(p['op'] == 'remove' for p in patch))):
            raise exception.PatchError(
                reason='Every op must be add or remove')

        for p in patch:
            path = p['path'].lstrip('/')
            if path not in valid_fields.keys():
                reason = 'Invalid path in patch {}'.format(p['path'])
                raise exception.PatchError(reason=reason)
            if p['op'] == 'add':
                valid_fields[path] = p['value']
        not_found = [field for field, value in valid_fields.items()
                     if value is None]
        if p['op'] == 'add' and len(not_found) > 0:
            msg = ','.join(not_found)
            reason = 'Fields absent in patch {}'.format(msg)
            raise exception.PatchError(reason=reason)
        return valid_fields

    # @policy.authorize_wsgi("cyborg:arq", "update")
    @expose.expose(None, body=types.jsontype,
                   status_code=http_client.ACCEPTED)
    def patch(self, patch_list):
        """Bind/Unbind an ARQ.

        Usage: curl -X PATCH .../v2/accelerator_requests
                 -d <patch_list> -H "Content-type: application/json"

        :param patch_list: A map from ARQ UUIDs to their JSON patches:
            {"$arq_uuid": [
                {"path": "/hostname", "op": ADD/RM, "value": "..."},
                {"path": "/device_rp_uuid", "op": ADD/RM, "value": "..."},
                {"path": "/instance_uuid", "op": ADD/RM, "value": "..."},
               ],
             "$arq_uuid": [...]
            }
            In particular, all and only these 3 fields must be present,
            and only 'add' or 'remove' ops are allowed.
        """
        LOG.info('[arqs] patch. list=(%s)', patch_list)
        context = pecan.request.context
        # Validate all patches before un/binding.
        valid_fields = {}
        for arq_uuid, patch in patch_list.items():
            valid_fields[arq_uuid] = self._validate_arq_patch(patch)

        # TODO Defer to conductor and do all concurently.
        for arq_uuid, patch in patch_list.items():
            extarq = objects.ExtARQ.get(context, arq_uuid)
            if patch[0]['op'] == 'add':  # All ops are 'add'
                extarq.bind(context,
                            valid_fields[arq_uuid]['hostname'],
                            valid_fields[arq_uuid]['device_rp_uuid'],
                            valid_fields[arq_uuid]['instance_uuid'])
            else:
                extarq.unbind(context)
