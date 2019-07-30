# -*- encoding: utf-8 -*-
# Copyright (c) 2019 ZTE Corporation
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

from oslo_log import log as logging
from oslo_serialization import jsonutils
from oslo_versionedobjects import base as object_base

from cyborg.db import api as dbapi
from cyborg.objects import base
from cyborg.objects import fields as object_fields


LOG = logging.getLogger(__name__)


@base.CyborgObjectRegistry.register
class DeviceProfile(base.CyborgObject, object_base.VersionedObjectDictCompat):
    # Version 1.0: Initial version
    VERSION = '1.0'

    dbapi = dbapi.get_instance()

    fields = {
        'id': object_fields.IntegerField(nullable=False),
        'uuid': object_fields.StringField(nullable=False),
        'name': object_fields.StringField(nullable=False),
        'groups': object_fields.ListOfDictOfNullableStringsField(),
    }

    def _to_profile_json(self, obj_changes):
        assert 'groups' in obj_changes
        if 'groups' in obj_changes:  # Convert to profile_json string
            d = {"groups": obj_changes['groups']}
            profile_json = jsonutils.dumps(d)
            obj_changes['profile_json'] = profile_json
            obj_changes.pop('groups', None)  # del 'groups'

    def create(self, context):
        """Create a Device Profile record in the DB."""
        # TODO validate with a JSON schema
        if 'name' not in self:
            raise exception.ObjectActionError(action='create',
                                              reason='name is required')

        values = self.obj_get_changes()
        self._to_profile_json(values)

        db_devprof = self.dbapi.device_profile_create(context, values)
        self._from_db_object(self, db_devprof)

    @classmethod
    def get(cls, context, name):
        """Find a DB Device Profile and return an Obj Device Profile."""
        db_devprof = cls.dbapi.device_profile_get(context, name)
        obj_devprof = cls._from_db_object(cls(context), db_devprof)
        return obj_devprof

    @classmethod
    def list(cls, context):
        """Return a list of Device Profile objects."""
        db_devprofs = cls.dbapi.device_profile_list(context)
        obj_dp_list = cls._from_db_object_list(db_devprofs, context)
        return obj_dp_list

    def save(self, context):
        """Update a Device Profile record in the DB."""
        updates = self.obj_get_changes()
        self._to_profile_json(updates)

        db_devprof = self.dbapi.device_profile_update(context,
                                                      self.name, updates)
        self._from_db_object(self, db_devprof)

    def destroy(self, context):
        """Delete a Device Profile from the DB."""
        self.dbapi.device_profile_delete(context, self.name)
        self.obj_reset_changes()

    @classmethod
    def _from_db_object(cls, obj, db_obj):
        """Converts a device_profile to a formal object.

        :param obj: An object of the class.
        :param db_obj: A DB model of the object
        :return: The object of the class with the database entity added
        """
        # Convert from profile_json to 'groups' ListOfDictOfStrings
        d = jsonutils.loads(db_obj['profile_json'])
        db_obj['groups'] = d['groups']
        # db_obj.pop('profile_json', None)

        obj = base.CyborgObject._from_db_object(obj, db_obj)
        return obj
