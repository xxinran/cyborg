# Copyright 2019 Beijing Lenovo Software Ltd.
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

from openstack import connection
from oslo_log import log as logging
from oslo_versionedobjects import base as object_base

from cyborg.agent.rpcapi import AgentAPI
from cyborg.db import api as dbapi
from cyborg.common import constants
from cyborg.common import exception
from cyborg.common import placement_client
from cyborg import objects
from cyborg.objects import base
from cyborg.objects.device_profile import DeviceProfile
from cyborg.objects import fields as object_fields

import subprocess

LOG = logging.getLogger(__name__)


@base.CyborgObjectRegistry.register
class ExtARQ(base.CyborgObject, object_base.VersionedObjectDictCompat):
    """ ExtARQ is a wrapper around ARQ with Cyborg-private fields.
        Each ExtARQ object contains exactly one ARQ object as a field.
        But, in the db layer, ExtARQ and ARQ are represented together
        as a row in a single table. Both share a single UUID.

        ExtARQ version is bumped up either if any of its fields change
        or if the ARQ version changes.
    """
    # Version 1.0: Initial version
    VERSION = '1.0'

    dbapi = dbapi.get_instance()

    fields = {
        'arq': object_fields.ObjectField('ARQ'),
        # Cyborg-private fields
        # Left substate open now, fill them out during design/implementation
        # later.
        'substate': object_fields.StringField(),
        'deployable_uuid': object_fields.StringField(),

        # The dp group is copied in to the extarq, so that any changes or
        # deletions to the device profile do not affect running VMs.
        'device_profile_group': object_fields.DictOfStringsField(
            nullable=True),
    }

    def create(self, context, device_profile_id=None):
        """Create an ExtARQ record in the DB."""
        if 'device_profile_name' not in self.arq and not device_profile_id:
            raise exception.ObjectActionError(
                action='create',
                reason='Device profile name is required in ARQ')
        self.arq.state = constants.ARQ_INITIAL
        self.substate = constants.ARQ_INITIAL
        values = self.obj_get_changes()
        arq_obj = values.pop('arq', None)
        if arq_obj is not None:
            values.update(arq_obj.as_dict())

        # Pass devprof id to db layer, to avoid repeated queries
        if device_profile_id is not None:
            values['device_profile_id'] = device_profile_id

        db_extarq = self.dbapi.extarq_create(context, values)
        self._from_db_object(self, db_extarq, context)
        return self

    @classmethod
    def get(cls, context, uuid):
        """Find a DB ExtARQ and return an Obj ExtARQ."""
        db_extarq = cls.dbapi.extarq_get(context, uuid)
        obj_arq = objects.ARQ(context)
        obj_extarq = ExtARQ(context)
        obj_extarq['arq'] = obj_arq
        obj_extarq = cls._from_db_object(obj_extarq, db_extarq, context)
        return obj_extarq

    @classmethod
    def list(cls, context):
        """Return a list of ExtARQ objects."""
        db_extarqs = cls.dbapi.extarq_list(context)
        obj_extarq_list = cls._from_db_object_list(db_extarqs, context)
        return obj_extarq_list

    def save(self, context):
        """Update an ExtARQ record in the DB."""
        updates = self.obj_get_changes()
        db_extarq = self.dbapi.extarq_update(context, self.arq.uuid, updates)
        self._from_db_object(self, db_extarq, context)

    def destroy(self, context):
        """Delete an ExtARQ from the DB."""
        self.dbapi.extarq_delete(context, self.arq.uuid)
        self.obj_reset_changes()

    def _get_bitstream_md_from_function_id(self, function_id):
        """Get bitstream metadata given a function id."""

        conn = connection.Connection(cloud='devstack-admin')
        properties = {'accel:function_id': function_id}
        resp = conn.image.get('/images', params=properties)
        if resp:
            image_list = resp.json()['images']
            assert isinstance(image_list, list)
            if len(image_list) != 1:
                raise exception.ExpectedOneObject(obj='image',
                                                  count=len(image_list))
            return image_list[0]
        else:
            LOG.warning('Failed to get image for function (%s)',
                        function_id)
            return None

    def _get_bitstream_md_from_bitstream_id(self, bitstream_id):
        """Get bitstream metadata given a bitstream id."""
        conn = connection.Connection(cloud='devstack-admin')
        resp = conn.image.get('/images/' + bitstream_id)
        if resp:
            return resp.json()
        else:
            LOG.warning('Failed to get image for bitstream (%s)',
                        bitstream_id)
            return None

    def _do_programming(self, context, hostname,
                        db_deployable, bitstream_id):
        """ TODO add this
        if db_deployable.num_accelerators_in_use > 0:
            raise RuntimeError('Programming needed but deployable ' +
                               '%s in use' % db_deployable.uuid)
        """
        driver_name = db_deployable.driver_name

        query_filter = {"device_id": db_deployable.device_id}
        cpid_list = self.dbapi.control_path_get_by_filters(
            context, query_filter)
        assert len(cpid_list) == 1
        controlpath_id = cpid_list[0]
        LOG.info('Found control path id: %s', controlpath_id.__dict__)

        LOG.info('Starting programming for host: (%s) deployable (%s) '
                 'bitstream_id (%s)', hostname,
                 db_deployable.uuid, bitstream_id)
        agent = AgentAPI()
        # TODO do this asynchronously
        agent.fpga_program_v2(context, hostname,
                              controlpath_id, bitstream_id,
                              driver_name)
        LOG.info('Finished programming for host: (%s) deployable (%s)',
                 hostname, db_deployable.uuid)
        # TODO propagate agent errors to caller
        return True

    def bind(self, context, hostname, devrp_uuid, instance_uuid):
        """ Given a device rp UUID, get the deployable UUID and
            an attach handle.
        """
        LOG.info('[arqs:objs] bind. hostname: %s, devrp_uuid: %s'
                 'instance: %s', hostname, devrp_uuid, instance_uuid)
        arq = self.arq
        arq.hostname = hostname
        arq.device_rp_uuid = devrp_uuid
        arq.instance_uuid = instance_uuid

        db_deployable = self.dbapi.deployable_get_by_rp_uuid(
            context, devrp_uuid)
        # TODO  Check that deployable.device.hostname matches param hostname

        bitstream_id = self.device_profile_group.get('accel:bitstream_id')
        function_id = self.device_profile_group.get('accel:function_id')
        programming_needed = (bitstream_id is not None or
                              function_id is not None)

        arq.state = constants.ARQ_BOUND  # If prog fails, we'll change this
        if programming_needed:
            LOG.info('[arqs:objs] bind. Programming needed. '
                     'bitstream: (%s) function: (%s) Deployable UUID: (%s)',
                     bitstream_id or '', function_id or '',
                     db_deployable.uuid)
            if bitstream_id is not None:  # FPGA aaS
                assert function_id is None
                bitstream_md = self._get_bitstream_md_from_bitstream_id(
                    bitstream_id)
            else:  # Accelerated Function aaS
                assert bitstream_id is None
                bitstream_md = self._get_bitstream_md_from_function_id(
                    function_id)
                LOG.info('[arqs:objs] For function id (%s), got '
                         'bitstream id (%s)', function_id,
                         bitstream_md['id'])
            assert bitstream_md is not None
            bitstream_id = bitstream_md['id']

            ok = self._do_programming(context, hostname,
                                      db_deployable, bitstream_id)
            if ok:
                placement_client.delete_traits_with_prefixes(
                    devrp_uuid, ['CUSTOM_FUNCTION_ID'])
                # TODO DO NOT apply function trait if bitstream is private
                if not function_id:
                    function_id = bitstream_md.get('accel:function_id')
                if function_id:
                    function_id = function_id.upper().replace('-', '_-')
                    # TODO Validate this is a valid trait name
                    trait_names = ['CUSTOM_FUNCTION_ID_' + function_id]
                    placement_client.add_traits_to_rp(devrp_uuid,
                                                      trait_names)
            else:
                arq.state = constants.ARQ_BIND_FAILED

        # FIXME db_deployable.num_accelerators_in_use += 1
        # FIXME write deployable to db
        self.save(context)  # ARQ state changes get committed here

    def unbind(self, context):
        arq = self.arq
        arq.hostname = ''
        arq.device_rp_uuid = ''
        arq.instance_uuid = ''
        arq.state = constants.ARQ_UNBOUND

        self.save(context)

    @classmethod
    def _fill_obj_extarq_fields(cls, context, db_extarq):
        """ ExtARQ object has some fields that are not present
            in db_extarq. We fill them out here.
        """
        # From the 2 fields in the ExtARQ, we obtain other fields.
        devprof_id = db_extarq['device_profile_id']
        devprof_group_id = db_extarq['device_profile_group_id']

        devprof = cls.dbapi.device_profile_get_by_id(context, devprof_id)
        db_extarq['device_profile_name'] = devprof['name']

        db_extarq['attach_handle_type'] = ''
        db_extarq['attach_handle_info'] = ''
        if db_extarq['state'] == 'Bound':  # TODO Do proper bind
            db_ah = cls.dbapi.attach_handle_get_by_type(context, 'PCI')
            if db_ah is not None:
                db_extarq['attach_handle_type'] = db_ah['attach_type']
                db_extarq['attach_handle_info'] = db_ah['attach_info']

        # TODO Get the deployable_uuid
        db_extarq['deployable_uuid'] = ''

        # Get the device profile group
        obj_devprof = DeviceProfile.get(context, devprof['name'])
        groups = obj_devprof['groups']
        db_extarq['device_profile_group'] = groups[devprof_group_id]

        return db_extarq

    @classmethod
    def _from_db_object(cls, extarq, db_extarq, context):
        """Converts an ExtARQ to a formal object.

        :param extarq: An object of the class ExtARQ
        :param db_extarq: A DB model of the object
        :return: The object of the class with the database entity added
        """
        cls._fill_obj_extarq_fields(context, db_extarq)

        for field in extarq.fields:
            if field != 'arq':
                extarq[field] = db_extarq[field]
        extarq.arq = objects.ARQ()
        extarq.arq._from_db_object(extarq.arq, db_extarq)
        extarq.obj_reset_changes()
        return extarq

    @classmethod
    def _from_db_object_list(cls, db_objs, context):
        """Converts a list of ExtARQs to a list of formal objects."""
        objs = []
        for db_obj in db_objs:
            objs.append(cls._from_db_object(cls(context), db_obj, context))
        return objs

    def obj_get_changes(self):
        """Returns a dict of changed fields and their new values."""
        changes = {}
        for key in self.obj_what_changed():
            if key != 'arq':
                changes[key] = getattr(self, key)

        for key in self.arq.obj_what_changed():
            changes[key] = getattr(self.arq, key)

        return changes
