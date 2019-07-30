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

"""Cyborg base exception handling.

SHOULD include dedicated exception logging.

"""

from oslo_log import log
import six
from six.moves import http_client

from cyborg.common.i18n import _
from cyborg.conf import CONF


LOG = log.getLogger(__name__)


class CyborgException(Exception):
    """Base Cyborg Exception

    To correctly use this class, inherit from it and define
    a '_msg_fmt' property. That message will get printf'd
    with the keyword arguments provided to the constructor.

    If you need to access the message from an exception you should use
    six.text_type(exc)

    """
    _msg_fmt = _("An unknown exception occurred.")
    code = http_client.INTERNAL_SERVER_ERROR
    headers = {}
    safe = False

    def __init__(self, message=None, **kwargs):
        self.kwargs = kwargs

        if 'code' not in self.kwargs:
            try:
                self.kwargs['code'] = self.code
            except AttributeError:
                pass

        if not message:
            try:
                message = self._msg_fmt % kwargs
            except Exception:
                # kwargs doesn't match a variable in self._msg_fmt
                # log the issue and the kwargs
                LOG.exception('Exception in string format operation')
                for name, value in kwargs.items():
                    LOG.error("%s: %s" % (name, value))

                if CONF.fatal_exception_format_errors:
                    raise
                else:
                    # at least get the core self._msg_fmt out if something
                    # happened
                    message = self._msg_fmt

        super(CyborgException, self).__init__(message)

    def __str__(self):
        """Encode to utf-8 then wsme api can consume it as well."""
        if not six.PY3:
            return unicode(self.args[0]).encode('utf-8')

        return self.args[0]

    def __unicode__(self):
        """Return a unicode representation of the exception message."""
        return unicode(self.args[0])


class ARQInvalidState(CyborgException):
    _msg_fmt = _("Accelerator Requests cannot be requested with "
                 "state %(state)s.")


class AttachHandleAlreadyExists(CyborgException):
    _msg_fmt = _("AttachHandle with uuid %(uuid)s already exists.")


class ControlpathIDAlreadyExists(CyborgException):
    _msg_fmt = _("ControlpathID with uuid %(uuid)s already exists.")


class ConfigInvalid(CyborgException):
    _msg_fmt = _("Invalid configuration file. %(error_msg)s")


class DeviceAlreadyExists(CyborgException):
    _msg_fmt = _("Device with uuid %(uuid)s already exists.")


class DeviceProfileAlreadyExists(CyborgException):
    _msg_fmt = _("DeviceProfile with uuid %(uuid)s already exists.")


class DeviceProfileNameNotFound(CyborgException):
    _msg_fmt = _("DeviceProfile with name %(name)s not found.")


class DeviceProfileNameNeeded(CyborgException):
    _msg_fmt = _("DeviceProfile name needed.")


class DeployableAlreadyExists(CyborgException):
    _msg_fmt = _("Deployable with uuid %(uuid)s already exists.")


class ExtArqAlreadyExists(CyborgException):
    _msg_fmt = _("ExtArq with uuid %(uuid)s already exists.")


class ExpectedOneObject(CyborgException):
    _msg_fmt = _("Expected one object of type %(obj)s "
                 "but got %(count)s.")


class InUse(CyborgException):
    _msg_fmt = _("%(object) with %(ident)s is in use.")


class Invalid(CyborgException):
    _msg_fmt = _("Invalid parameters.")
    code = http_client.BAD_REQUEST


class InvalidIdentity(Invalid):
    _msg_fmt = _("Expected a uuid/id but received %(identity)s.")


class InvalidUUID(Invalid):
    _msg_fmt = _("Expected a uuid but received %(uuid)s.")


class InvalidJsonType(Invalid):
    _msg_fmt = _("%(value)s is not JSON serializable.")


# Cannot be templated as the error syntax varies.
# msg needs to be constructed when raised.
class InvalidParameterValue(Invalid):
    _msg_fmt = _("%(err)s")


class NeedAtleastOne(Invalid):
    _msg_fmt = _("Need at least one %(obj)s.")


class PatchError(Invalid):
    _msg_fmt = _("Couldn't apply patch '%(patch)s'. Reason: %(reason)s")


class NotAuthorized(CyborgException):
    _msg_fmt = _("Not authorized.")
    code = http_client.FORBIDDEN


class HTTPForbidden(NotAuthorized):
    _msg_fmt = _("Access was denied to the following resource: %(resource)s")


class NotFound(CyborgException):
    _msg_fmt = _("Resource could not be found.")
    code = http_client.NOT_FOUND


class ServiceNotFound(NotFound):
    msg_fmt = _("Service %(service_id)s could not be found.")


class AttachHandleNotFound(NotFound):
    _msg_fmt = _("AttachHandle %(uuid)s could not be found.")


class ControlpathIDNotFound(NotFound):
    _msg_fmt = _("ControlpathID %(uuid)s could not be found.")


class ConfGroupForServiceTypeNotFound(ServiceNotFound):
    msg_fmt = _("No conf group name could be found for service type "
                "%(stype)s.")


class DeviceNotFound(NotFound):
    _msg_fmt = _("Device %(uuid)s could not be found.")


class DeviceProfileNotFound(NotFound):
    _msg_fmt = _("DeviceProfile %(uuid)s could not be found.")


class DeployableNotFound(NotFound):
    _msg_fmt = _("Deployable %(uuid)s could not be found.")


class ExtArqNotFound(NotFound):
    _msg_fmt = _("ExtArq %(uuid)s could not be found.")


class InvalidDeployType(CyborgException):
    _msg_fmt = _("Deployable have an invalid type")


class Conflict(CyborgException):
    _msg_fmt = _('Conflict.')
    code = http_client.CONFLICT


class DuplicateDeviceName(Conflict):
    _msg_fmt = _("A device with name %(name)s already exists.")


class DuplicateDeviceProfileName(Conflict):
    _msg_fmt = _("A device_profile with name %(name)s already exists.")


class DuplicateDeployableName(Conflict):
    _msg_fmt = _("A deployable with name %(name)s already exists.")


class PlacementEndpointNotFound(NotFound):
    message = _("Placement API endpoint not found")


class PlacementResourceProviderNotFound(NotFound):
    message = _("Placement resource provider not found %(resource_provider)s.")


class PlacementInventoryNotFound(NotFound):
    message = _("Placement inventory not found for resource provider "
                "%(resource_provider)s, resource class %(resource_class)s.")


class PlacementInventoryUpdateConflict(Conflict):
    message = _("Placement inventory update conflict for resource provider "
                "%(resource_provider)s, resource class %(resource_class)s.")


class ObjectActionError(CyborgException):
    _msg_fmt = _('Object action %(action)s failed because: %(reason)s')


class AttributeNotFound(NotFound):
    _msg_fmt = _("Attribute %(uuid)s could not be found.")


class AttributeInvalid(CyborgException):
    _msg_fmt = _("Attribute is invalid")


class AttributeAlreadyExists(CyborgException):
    _msg_fmt = _("Attribute with uuid %(uuid)s already exists.")


# An exception with this name is used on both sides of the placement/
# cyborg interaction.
class ResourceClassNotFound(NotFound):
    msg_fmt = _("No such resource class %(name_or_uuid)s.")


class ResourceProviderInUse(CyborgException):
    msg_fmt = _("Resource provider has allocations.")


class ResourceProviderRetrievalFailed(CyborgException):
    msg_fmt = _("Failed to get resource provider with UUID %(uuid)s")


class ResourceProviderAggregateRetrievalFailed(CyborgException):
    msg_fmt = _("Failed to get aggregates for resource provider with UUID"
                " %(uuid)s")


class ResourceProviderTraitRetrievalFailed(CyborgException):
    msg_fmt = _("Failed to get traits for resource provider with UUID"
                " %(uuid)s")


class ResourceProviderCreationFailed(CyborgException):
    msg_fmt = _("Failed to create resource provider %(name)s")


class ResourceProviderDeletionFailed(CyborgException):
    msg_fmt = _("Failed to delete resource provider %(uuid)s")


class ResourceProviderUpdateFailed(CyborgException):
    msg_fmt = _("Failed to update resource provider via URL %(url)s: "
                "%(error)s")


class ResourceProviderNotFound(NotFound):
    msg_fmt = _("No such resource provider %(name_or_uuid)s.")


class ResourceProviderSyncFailed(CyborgException):
    msg_fmt = _("Failed to synchronize the placement service with resource "
                "provider information supplied by the compute host.")


class PlacementAPIConnectFailure(CyborgException):
    msg_fmt = _("Unable to communicate with the Placement API.")


class PlacementAPIConflict(CyborgException):
    """Any 409 error from placement APIs should use (a subclass of) this
    exception.
    """
    msg_fmt = _("A conflict was encountered attempting to invoke the "
                "placement API at URL %(url)s: %(error)s")


class ResourceProviderUpdateConflict(PlacementAPIConflict):
    """A 409 caused by generation mismatch from attempting to update an
    existing provider record or its associated data (aggregates, traits, etc.).
    """
    msg_fmt = _("A conflict was encountered attempting to update resource "
                "provider %(uuid)s (generation %(generation)d): %(error)s")


class TraitCreationFailed(CyborgException):
    msg_fmt = _("Failed to create trait %(name)s: %(error)s")


class TraitRetrievalFailed(CyborgException):
    msg_fmt = _("Failed to retrieve traits from the placement API: %(error)s")


class InvalidResourceClass(Invalid):
    msg_fmt = _("Resource class '%(resource_class)s' invalid.")


class InvalidResourceAmount(Invalid):
    msg_fmt = _("Resource amounts must be integers. Received '%(amount)s'.")


class InvalidInventory(Invalid):
    msg_fmt = _("Inventory for '%(resource_class)s' on "
                "resource provider '%(resource_provider)s' invalid.")


# An exception with this name is used on both sides of the placement/
# cyborg interaction.
class InventoryInUse(InvalidInventory):
    # NOTE(mriedem): This message cannot change without impacting the
    # cyborg.services.client.report._RE_INV_IN_USE regex.
    msg_fmt = _("Inventory for '%(resource_classes)s' on "
                "resource provider '%(resource_provider)s' in use.")


class QuotaNotFound(NotFound):
    message = _("Quota could not be found")


class QuotaUsageNotFound(QuotaNotFound):
    message = _("Quota usage for project %(project_id)s could not be found.")


class QuotaResourceUnknown(QuotaNotFound):
    message = _("Unknown quota resources %(unknown)s.")


class InvalidReservationExpiration(Invalid):
    message = _("Invalid reservation expiration %(expire)s.")


class GlanceConnectionFailed(CyborgException):
    msg_fmt = _("Connection to glance host %(server)s failed: "
                "%(reason)s")


class ImageUnacceptable(Invalid):
    msg_fmt = _("Image %(image_id)s is unacceptable: %(reason)s")


class ImageNotAuthorized(CyborgException):
    msg_fmt = _("Not authorized for image %(image_id)s.")


class ImageNotFound(NotFound):
    msg_fmt = _("Image %(image_id)s could not be found.")


class ImageBadRequest(Invalid):
    msg_fmt = _("Request of image %(image_id)s got BadRequest response: "
                "%(response)s")


class InvalidDriver(Invalid):
    _msg_fmt = _("Found an invalid driver: %(name)s")
