# Copyright 2017 Huawei Technologies Co.,LTD.
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

import oslo_messaging as messaging
import socket
import uuid
import re


from cyborg.common import rc_fields
from cyborg.conf import CONF
from cyborg.common import exception
from cyborg import objects
from cyborg.objects.deployable import Deployable
from cyborg.objects.device import Device
from cyborg.objects.attribute import Attribute
from cyborg.objects.attach_handle import AttachHandle
from cyborg.objects.control_path import ControlpathID
from cyborg.objects.driver_objects.driver_device import DriverDevice
from cyborg.services.client import report as placement_report_client

from oslo_log import log as logging
LOG = logging.getLogger(__name__)

RC_FPGA = rc_fields.ResourceClass.normalize_name(
    rc_fields.ResourceClass.FPGA)

RESOURCES = {
    "FPGA": RC_FPGA
}


class ConductorManager(object):
    """Cyborg Conductor manager main class."""

    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, topic, host=None):
        super(ConductorManager, self).__init__()
        self.topic = topic
        self.host = host or CONF.host
        self.p_client = placement_report_client.SchedulerReportClient()

    def periodic_tasks(self, context, raise_on_error=False):
        pass

    def accelerator_create(self, context, obj_acc):
        """Create a new accelerator.

        :param context: request context.
        :param obj_acc: a changed (but not saved) accelerator object.
        :returns: created accelerator object.
        """
        base_options = {
            'project_id': context.tenant,
            'user_id': context.user
            }
        obj_acc.update(base_options)
        obj_acc.create(context)
        return obj_acc

    def accelerator_update(self, context, obj_acc):
        """Update an accelerator.

        :param context: request context.
        :param obj_acc: an accelerator object to update.
        :returns: updated accelerator object.
        """
        obj_acc.save(context)
        return obj_acc

    def accelerator_delete(self, context, obj_acc):
        """Delete an accelerator.

        :param context: request context.
        :param obj_acc: an accelerator object to delete.
        """
        obj_acc.destroy(context)

    def deployable_create(self, context, obj_dep):
        """Create a new deployable.

        :param context: request context.
        :param obj_dep: a changed (but not saved) obj_dep object.
        :returns: created obj_dep object.
        """
        obj_dep.create(context)
        return obj_dep

    def deployable_update(self, context, obj_dep):
        """Update a deployable.

        :param context: request context.
        :param obj_dep: a deployable object to update.
        :returns: updated deployable object.
        """
        obj_dep.save(context)
        return obj_dep

    def deployable_delete(self, context, obj_dep):
        """Delete a deployable.

        :param context: request context.
        :param obj_dep: a deployable object to delete.
        """
        obj_dep.destroy(context)

    def deployable_get(self, context, uuid):
        """Retrieve a deployable.

        :param context: request context.
        :param uuid: UUID of a deployable.
        :returns: requested deployable object.
        """
        return objects.Deployable.get(context, uuid)

    def deployable_list(self, context):
        """Retrieve a list of deployables.

        :param context: request context.
        :returns: a list of deployable objects.
        """
        return objects.Deployable.list(context)

    def report_data(self, context, hostname, driver_device_list):
        """Update the Cyborg DB in one hostname according to the
        discovered device list.
        :param context: request context.
        :param hostname: agent's hostname.
        :param driver_device_list: a list of driver_device object
        discovered by agent in the host.
        """
        # TODO: Everytime get from the DB?
        # First retrieve the old_device_list from the DB.
        old_driver_device_list = DriverDevice.list(context, hostname)
        # TODO(wangzhh): Remove invalid driver_devices without controlpath_id.
        # Then diff two driver device list.
        self.drv_device_make_diff(context, hostname,
                                  old_driver_device_list, driver_device_list)

    def drv_device_make_diff(self, context, host, old_driver_device_list,
                             new_driver_device_list):
        """Compare new driver-side device object list with the old one in
        one host."""
        LOG.info("Start differing devices.")
        # TODO:The placement report will be implemented here.
        # Use cpid.cpid_info to identify whether the device is the same.
        new_cpid_list = [driver_dev_obj.controlpath_id.cpid_info for
                         driver_dev_obj in new_driver_device_list]
        old_cpid_list = [driver_dev_obj.controlpath_id.cpid_info for
                         driver_dev_obj in old_driver_device_list]
        same = set(new_cpid_list) & set(old_cpid_list)
        added = set(new_cpid_list) - same
        deleted = set(old_cpid_list) - same
        for s in same:
            # get the driver_dev_obj, diff the driver_device layer
            new_driver_dev_obj = new_driver_device_list[new_cpid_list.index(s)]
            old_driver_dev_obj = old_driver_device_list[old_cpid_list.index(s)]
            # First, get dev_obj_list from hostname
            device_obj_list = Device.get_list_by_hostname(context, host)
            # Then, use controlpath_id.cpid_info to identiy one Device.
            cpid_info = new_driver_dev_obj.controlpath_id.cpid_info
            for dev_obj in device_obj_list:
                # get cpid_obj, could be empty or only one value.
                cpid_obj = ControlpathID.get_by_device_id_cpidinfo(
                    context, dev_obj.id, cpid_info)
                # find the one cpid_obj with cpid_info
                if cpid_obj is not None:
                    break

            changed_key = ['std_board_info', 'vendor', 'vendor_board_info',
                           'model', 'type']
            for c_k in changed_key:
                if getattr(new_driver_dev_obj, c_k) != getattr(
                        old_driver_dev_obj, c_k):
                    setattr(dev_obj, c_k, getattr(new_driver_dev_obj, c_k))
            dev_obj.save(context)
            # diff the internal layer: driver_deployable
            self.drv_deployable_make_diff(context, dev_obj.id, cpid_obj.id,
                                          old_driver_dev_obj.deployable_list,
                                          new_driver_dev_obj.deployable_list)
        # device is deleted.
        for d in deleted:
            old_driver_dev_obj = old_driver_device_list[old_cpid_list.index(d)]
            rp_uuid = self.get_pr_uuid_from_obj(old_driver_dev_obj)
            old_driver_dev_obj.destroy(context, host)
            self._delete_provider_and_sub_providers(context, rp_uuid)
        # device is added
        for a in added:
            new_driver_dev_obj = new_driver_device_list[new_cpid_list.index(a)]
            new_driver_dev_obj.create(context, host)
            # create_provider here.
            self.get_placement_needed_info_and_report(context,
                                                      new_driver_dev_obj)

    @classmethod
    def drv_deployable_make_diff(cls, context, device_id, cpid_id,
                                 old_driver_dep_list, new_driver_dep_list):
        """Compare new driver-side deployable object list with the old one in
        one host."""
        # use name to identify whether the deployable is the same.
        LOG.info("Start differing deploybles.")
        new_name_list = [driver_dep_obj.name for driver_dep_obj in
                         new_driver_dep_list]
        old_name_list = [driver_dep_obj.name for driver_dep_obj in
                         old_driver_dep_list]
        same = set(new_name_list) & set(old_name_list)
        added = set(new_name_list) - same
        deleted = set(old_name_list) - same
        for s in same:
            # get the driver_dep_obj, diff the driver_dep layer
            new_driver_dep_obj = new_driver_dep_list[new_name_list.index(s)]
            old_driver_dep_obj = old_driver_dep_list[old_name_list.index(s)]
            # get dep_obj, it won't be None because it stored before.
            dep_obj = Deployable.get_by_name_deviceid(context, s, device_id)
            # update the driver_dep num_accelerators field
            if dep_obj.num_accelerators != new_driver_dep_obj.num_accelerators:
                # TODO(Xinran): Should update provider's inventory here.
                dep_obj.num_accelerators = new_driver_dep_obj.num_accelerators
                dep_obj.save(context)
            # diff the internal layer: driver_attribute_list
            new_attribute_list = []
            if hasattr(new_driver_dep_obj, 'attribute_list'):
                new_attribute_list = new_driver_dep_obj.attribute_list
            cls.drv_attr_make_diff(context, dep_obj.id,
                                   old_driver_dep_obj.attribute_list,
                                   new_attribute_list)
            # diff the internal layer: driver_attach_hanle_list
            cls.drv_ah_make_diff(context, dep_obj.id, cpid_id,
                                 old_driver_dep_obj.attach_handle_list,
                                 new_driver_dep_obj.attach_handle_list)
        # name is deleted.
        for d in deleted:
            # TODO(Xinran): Need to delete sub provider here.
            old_driver_dep_obj = old_driver_dep_list[old_name_list.index(d)]
            old_driver_dep_obj.destroy(context, device_id)
        # name is added.
        for a in added:
            # TODO(Xinran): Need to delete sub provider here.
            new_driver_dep_obj = new_driver_dep_list[new_name_list.index(a)]
            new_driver_dep_obj.create(context, device_id, cpid_id)

    @classmethod
    def drv_attr_make_diff(cls, context, dep_id, old_driver_attr_list,
                           new_driver_attr_list):
        # TODO(Xinran): Should update traits in this function.
        """Diff new dirver-side Attribute Object lists with the old one."""
        LOG.info("Start differing attributes.")
        new_key_list = [driver_attr_obj.key for driver_attr_obj in
                        new_driver_attr_list]
        old_key_list = [driver_attr_obj.key for driver_attr_obj in
                        old_driver_attr_list]
        same = set(new_key_list) & set(old_key_list)
        # key is same, diff the value.
        for s in same:
            # value is not same, update
            new_driver_attr_obj = new_driver_attr_list[new_key_list.index(s)]
            old_driver_attr_obj = old_driver_attr_list[old_key_list.index(s)]
            if new_driver_attr_obj.value != old_driver_attr_obj.value:
                attr_obj = Attribute.get_by_dep_key(context, dep_id, s)
                attr_obj.value = new_driver_attr_obj.value
                attr_obj.save(context)
        # key is deleted.
        deleted = set(old_key_list) - same
        for d in deleted:
            old_driver_attr_obj = old_driver_attr_list[old_key_list.index(d)]
            old_driver_attr_obj.delete_by_key(context, dep_id, d)
        # key is added.
        added = set(new_key_list) - same
        for a in added:
            new_driver_attr_obj = new_driver_attr_list[new_key_list.index(a)]
            new_driver_attr_obj.create(context, dep_id)

    @classmethod
    def drv_ah_make_diff(cls, context, dep_id, cpid_id, old_driver_ah_list,
                         new_driver_ah_list):
        """Diff new dirver-side AttachHandle Object lists with the old one."""
        LOG.info("Start differing attach_handles.")
        new_info_list = [driver_ah_obj.attach_info for driver_ah_obj in
                         new_driver_ah_list]
        old_info_list = [driver_ah_obj.attach_info for driver_ah_obj in
                         old_driver_ah_list]
        same = set(new_info_list) & set(old_info_list)
        LOG.info(new_info_list)
        LOG.info(old_info_list)
        # attach-info is same
        for s in same:
            # get attach_handle obj
            new_driver_ah_obj = new_driver_ah_list[new_info_list.index(s)]
            old_driver_ah_obj = old_driver_ah_list[old_info_list.index(s)]
            changed_key = ['in_use', 'attach_type']
            ah_obj = AttachHandle.get_ah_by_depid_attachinfo(context,
                                                             dep_id, s)
            for c_k in changed_key:
                if getattr(new_driver_ah_obj, c_k) != getattr(
                        old_driver_ah_obj, c_k):
                    # need update inventory here.
                    setattr(ah_obj, c_k, getattr(new_driver_ah_obj, c_k))
            ah_obj.save(context)
        # attach_info is deleted.
        deleted = set(old_info_list) - same
        for d in deleted:
            # update inventory here.
            old_driver_ah_obj = old_driver_ah_list[old_info_list.index(d)]
            old_driver_ah_obj.destroy(context, dep_id)
        # attach_info is added.
        added = set(new_info_list) - same
        for a in added:
            # update inventory here.
            new_driver_ah_obj = new_driver_ah_list[new_info_list.index(a)]
            new_driver_ah_obj.create(context, dep_id, cpid_id)

    def _get_root_provider(self):
        try:
            prvioder = self.p_client.get(
                "resource_providers?name=" + socket.gethostname()).json()
            pr_uuid = prvioder["resource_providers"][0]["uuid"]
            return pr_uuid
        except IndexError:
            print("Error, provider '%s' can not be found"
                  % socket.gethostname())
        except Exception as e:
            print("Error, could not access placement. Details: %s" % e)
        return

    def _get_sub_provider(self, context, parent, name):
        name = name.encode("utf-8")
        sub_pr_uuid = str(uuid.uuid3(uuid.NAMESPACE_DNS, name))
        sub_pr = self.p_client.get_provider_tree_and_ensure_root(
            context, sub_pr_uuid,
            name=name, parent_provider_uuid=parent)
        return sub_pr, sub_pr_uuid

    def provider_report(self, context, name, resource_class, traits, total,
                        parent):
        # need try:
        # if nova agent does start up, will not update placement.
        try:
            rs = self.p_client.get("/resource_classes/%s" % resource_class,
                                   version='1.26')
        except Exception as e:
            self.p_client.ensure_resource_classes(context, [resource_class])
            print("Error, could not access resource_classes. Details: %s" % e)

        # set_inventory_for_provider()
        # name = "dev : FPGA_PCI_ADDRESS /dep: intel-fpga-dev.2"
        # we can also get sub_pr_uuid by sub_pr.get_provider_uuids()[-1]
        sub_pr, sub_pr_uuid = self._get_sub_provider(
            context, parent, name)
        result = self._gen_resource_inventory(resource_class, total)
        sub_pr.update_inventory(name, result)
        # We need to normalize inventory data for the compute node provider
        # (inject allocation ratio and reserved amounts from the
        # compute_node record if not set by the virt driver) because the
        # virt driver does not and will not have access to the compute_node
        # inv_data = sub_pr.data(PR_NAME).inventory
        # _normalize_inventory_from_cn_obj(inv_data, compute_node)
        # sub_pr.update_inventory(PR_NAME, inv_data)
        # Flush any changes.
        self.p_client.update_from_provider_tree(context, sub_pr)
        # traits = ["CUSTOM_FPGA_INTEL", "CUSTOM_FPGA_INTEL_ARRIA10",
        #           "CUSTOM_FPGA_INTEL_REGION_UUID",
        #           "CUSTOM_FPGA_INTEL_FUNCTION_UUID",
        #           "CUSTOM_PROGRAMMABLE",
        #           "CUSTOM_FPGA_NETWORK"]
        self.p_client.set_traits_for_provider(context, sub_pr_uuid, traits)
        return sub_pr_uuid

    def get_placement_needed_info_and_report(self, context, obj,
                                             parent_uuid=None):
        # hostname provider
        root_provider = self._get_root_provider()
        if obj.obj_name() == "DriverDevice":
            pr_name = obj.type + "_" + re.sub(r'\W', "_",
                                              obj.controlpath_id.cpid_info)
            resource_class = RESOURCES.get(obj.type, None)
            if not resource_class:
                raise exception.ResourceClassNotFound()
            parent, parent_uuid = self._get_sub_provider(context,
                                                         root_provider,
                                                         pr_name)
            for driver_dep_obj in obj.deployable_list:
                self.get_placement_needed_info_and_report(context,
                                                          driver_dep_obj,
                                                          parent_uuid)
        elif obj.obj_name() == "DriverDeployable":
            pr_name = obj.name
            attrs = obj.attribute_list
            resource_class = [i.value for i in attrs if i.key == 'rc'][0]
            traits = [i.value for i in attrs
                      if i.key.encode('utf-8').startswith("trait")]
            total = obj.num_accelerators
            self.provider_report(context, pr_name, resource_class, traits,
                                 total, parent_uuid)
        else:
            raise exception.Invalid()

    def _gen_resource_inventory(self, name, total=0, max=1, min=1, step=1):
        result = {}
        result[name] = {
            'total': total,
            'min_unit': min,
            'max_unit': max,
            'step_size': step,
        }
        return result

    def get_pr_uuid_from_obj(self, obj):
        pr_name = obj.type + "_" + re.sub(r'\W', "_",
                                          obj.controlpath_id.cpid_info)
        pr_name = pr_name.encode("utf-8")
        return str(uuid.uuid3(uuid.NAMESPACE_DNS, pr_name))

    def _delete_provider_and_sub_providers(self, context, rp_uuid):
        rp_in_tree = self.p_client._get_providers_in_tree(context, rp_uuid)
        for rp in rp_in_tree[::-1]:
            if rp["parent_provider_uuid"] == rp_uuid or rp["uuid"] == rp_uuid:
                self.p_client._delete_provider(rp["uuid"])
                LOG.info("Sucessfully delete resource provider %s" %
                         rp["uuid"])
                if rp["uuid"] == rp_uuid:
                    break
