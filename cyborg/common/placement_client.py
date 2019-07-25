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

import copy

from oslo_log import log as logging
from oslo_middleware import request_id

from keystoneauth1 import exceptions as ks_exc
from cyborg.common import exception
from cyborg.common import rc_fields as fields
from cyborg.common import utils
from cyborg.conductor import provider_tree

LOG = logging.getLogger(__name__)
NESTED_PROVIDER_API_VERSION = '1.14'
POST_RPS_RETURNS_PAYLOAD_API_VERSION = '1.20'
PLACEMENT_API_RETURN_PROVIDER_BODY = 'placement 1.20'
PLACEMENT_API_LATEST_SUPPORTED = PLACEMENT_API_RETURN_PROVIDER_BODY
API_VERSION_REQUEST_HEADER = 'OpenStack-API-Version'
PLACEMENT_CLIENT_SEMAPHORE = 'placement_client'


class ReportClient(object):
    """Client class for reporting to placement."""

    def __init__(self, adapter=None,
                 openstack_api_version=PLACEMENT_API_LATEST_SUPPORTED):
        """Initialize the report client.

        :param adapter: A prepared keystoneauth1 Adapter for API communication.
                If unspecified, one is created based on config options in the
                [placement] section.
        """
        self._adapter = adapter
        # An object that contains a nova-compute-side cache of resource
        # provider and inventory information
        self._provider_tree = provider_tree.ProviderTree()
        # Track the last time we updated providers' aggregates and traits
        self._association_refresh_time = {}
        self._client = self._create_client()
        self._openstack_api_version = openstack_api_version
        self._api_version_header = {API_VERSION_REQUEST_HEADER:
                                    self._openstack_api_version}

    @utils.synchronized(PLACEMENT_CLIENT_SEMAPHORE)
    def _create_client(self):
        """Create the HTTP session accessing the placement service."""
        # Flush provider tree and associations so we start from a clean slate.
        self._provider_tree = provider_tree.ProviderTree()
        self._association_refresh_time = {}
        client = self._adapter or utils.get_ksa_adapter('placement')
        # Set accept header on every request to ensure we notify placement
        # service of our response body media type preferences.
        client.additional_headers = {'accept': 'application/json'}
        return client

    def _extend_header_with_api_version(self, **kwargs):
        headers = kwargs.get('headers', {})
        if API_VERSION_REQUEST_HEADER not in headers:
            if 'headers' not in kwargs:
                kwargs['headers'] = self._api_version_header
            else:
                kwargs['headers'].update(self._api_version_header)
        return kwargs

    def get(self, url, version=None, global_request_id=None):
        headers = ({request_id.INBOUND_HEADER: global_request_id}
                   if global_request_id else {})
        return self._client.get(url, microversion=version, headers=headers)

    def post(self, url, data, version=None, global_request_id=None):
        headers = ({request_id.INBOUND_HEADER: global_request_id}
                   if global_request_id else {})
        # NOTE(sdague): using json= instead of data= sets the
        # media type to application/json for us. Placement API is
        # more sensitive to this than other APIs in the OpenStack
        # ecosystem.
        return self._client.post(url, json=data, microversion=version,
                                 headers=headers)

    def put(self, url, data, version=None, global_request_id=None):
        # NOTE(sdague): using json= instead of data= sets the
        # media type to application/json for us. Placement API is
        # more sensitive to this than other APIs in the OpenStack
        # ecosystem.
        kwargs = {'microversion': version,
                  'headers': {request_id.INBOUND_HEADER:
                              global_request_id} if global_request_id else {}}
        if data is not None:
            kwargs['json'] = data
        return self._client.put(url, **kwargs)

    def delete(self, url, version=None, global_request_id=None):
        headers = ({request_id.INBOUND_HEADER: global_request_id}
                   if global_request_id else {})
        return self._client.delete(url, microversion=version, headers=headers)

    def _get_rp_traits(self, rp_uuid):
        # placement = _get_placement()
        resp = self.get("/resource_providers/%s/traits" % rp_uuid,
                        version='1.6')
        if resp.status_code != 200:
            raise Exception(
                "Failed to get traits for rp %s: HTTP %d: %s" %
                (rp_uuid, resp.status_code, resp.text))
        return resp.json()

    def _ensure_traits(self, trait_names):
        # placement = _get_placement()
        for trait in trait_names:
            resp = self.put("/traits/%s" % trait, None, version='1.6')
            if resp.status_code == 201:
                LOG.info("Created trait %s" % trait)
            elif resp.status_code == 204:
                LOG.info("Trait %s already existed" % trait)
            else:
                raise Exception(
                    "Failed to create trait %s: HTTP %d: %s" %
                    (trait, resp.status_code, resp.text))

    def _put_rp_traits(self, rp_uuid, traits_json):
        generation = self.get_resource_provider(
            resource_provider_uuid=rp_uuid)['generation']
        payload = {
            'resource_provider_generation': generation,
            'traits': traits_json["traits"],
        }
        resp = self.put(
            "/resource_providers/%s/traits" % rp_uuid, payload, version='1.6')
        if resp.status_code != 200:
            raise Exception(
                "Failed to set traits to %s for rp %s: HTTP %d: %s" %
                (traits_json, rp_uuid, resp.status_code, resp.text))
        elif resp.status_code == 200:
            json = resp.json()
            self._provider_tree.update_traits(
                rp_uuid, json['traits'],
                generation=json['resource_provider_generation'])
            return

    def add_traits_to_rp(self, rp_uuid, trait_names):
        self._ensure_traits(trait_names)
        traits_json = self._get_rp_traits(rp_uuid)
        traits = list(set(traits_json['traits'] + trait_names))
        traits_json['traits'] = traits
        self._put_rp_traits(rp_uuid, traits_json)

    def delete_trait_by_name(self, rp_uuid, trait_name):
        traits_json = self._get_rp_traits(rp_uuid)
        traits = [
            trait for trait in traits_json['traits']
            if trait != trait_name
            ]
        traits_json['traits'] = traits
        self._put_rp_traits(rp_uuid, traits_json)

    def delete_traits_with_prefixes(self, rp_uuid, trait_prefixes):
        traits_json = self._get_rp_traits(rp_uuid)
        traits = [
            trait for trait in traits_json['traits']
            if not any(trait.startswith(prefix)
                       for prefix in trait_prefixes)]
        traits_json['traits'] = traits
        self._put_rp_traits(rp_uuid, traits_json)

    def get_placement_request_id(self, response):
        if response is not None:
            return response.headers.get(request_id.HTTP_RESP_HEADER_REQUEST_ID)

    def _update_inventory(
            self, resource_provider_uuid, inventories,
            resource_provider_generation=None):
        if resource_provider_generation is None:
            resource_provider_generation = self.get_resource_provider(
                resource_provider_uuid=resource_provider_uuid)['generation']
        url = '/resource_providers/%s/inventories' % resource_provider_uuid
        body = {
            'resource_provider_generation': resource_provider_generation,
            'inventories': inventories
        }
        try:
            return self.put(url, body).json()
        except ks_exc.NotFound:
            raise exception.PlacementResourceProviderNotFound(
                resource_provider=resource_provider_uuid)

    def get_resource_provider(self, resource_provider_uuid):
        """Get resource provider by UUID.
        :param resource_provider_uuid: UUID of the resource provider.
        :raises PlacementResourceProviderNotFound: For failure to find resource
        :returns: The Resource Provider matching the UUID.
        """
        url = '/resource_providers/%s' % resource_provider_uuid
        try:
            return self.get(url).json()
        except ks_exc.NotFound:
            raise exception.PlacementResourceProviderNotFound(
                resource_provider=resource_provider_uuid)

    def _create_resource_provider(self, context, uuid, name,
                                  parent_provider_uuid=None):
        """Calls the placement API to create a new resource provider record.

        :param context: The security context
        :param uuid: UUID of the new resource provider
        :param name: Name of the resource provider
        :param parent_provider_uuid: Optional UUID of the immediate parent
        :return: A dict of resource provider information object representing
                 the newly-created resource provider.
        :raise: ResourceProviderCreationFailed or
                ResourceProviderRetrievalFailed on error.
        """
        url = "/resource_providers"
        payload = {
            'uuid': uuid,
            'name': name,
        }
        if parent_provider_uuid is not None:
            payload['parent_provider_uuid'] = parent_provider_uuid

        # Bug #1746075: First try the microversion that returns the new
        # provider's payload.
        resp = self.post(url, payload,
                         version=POST_RPS_RETURNS_PAYLOAD_API_VERSION,
                         global_request_id=context.global_id)

        placement_req_id = self.get_placement_request_id(resp)

        if resp:
            msg = ("[%(placement_req_id)s] Created resource provider record "
                   "via placement API for resource provider with UUID "
                   "%(uuid)s and name %(name)s.")
            args = {
                'uuid': uuid,
                'name': name,
                'placement_req_id': placement_req_id,
            }
            LOG.info(msg, args)
            return resp.json()

    def _ensure_resource_provider(self, context, uuid, name=None,
                                  parent_provider_uuid=None):
        created_rp = None
        rps_to_refresh = self._get_providers_in_tree(context, uuid)
        if not rps_to_refresh:
            created_rp = self._create_resource_provider(
                context, uuid, name or uuid,
                parent_provider_uuid=parent_provider_uuid)
            if created_rp is None:
                raise exception.ResourceProviderCreationFailed(
                    name=name or uuid)
            # Don't add the created_rp to rps_to_refresh.  Since we just
            # created it, it has no aggregates or traits.

        self._provider_tree.populate_from_iterable(
            rps_to_refresh or [created_rp])

        # At this point, the whole tree exists in the local cache.

        for rp_to_refresh in rps_to_refresh:
            # NOTE(efried): _refresh_associations doesn't refresh inventory
            # (yet) - see that method's docstring for the why.
            self._refresh_and_get_inventory(context, rp_to_refresh['uuid'])
        return uuid

    def _refresh_and_get_inventory(self, context, rp_uuid):
        """Helper method that retrieves the current inventory for the supplied
        resource provider according to the placement API.

        If the cached generation of the resource provider is not the same as
        the generation returned from the placement API, we update the cached
        generation and attempt to update inventory if any exists, otherwise
        return empty inventories.
        """
        curr = self._get_inventory(context, rp_uuid)
        if curr is None:
            return None

        cur_gen = curr['resource_provider_generation']
        # TODO(efried): This condition banks on the generation for a new RP
        # starting at zero, which isn't part of the API.  It also is only
        # useful as an optimization on a freshly-created RP to which nothing
        # has ever been done.  And it's not much of an optimization, because
        # updating the cache is super cheap.  We should remove the condition.
        if cur_gen:
            curr_inv = curr['inventories']
            self._provider_tree.update_inventory(rp_uuid, curr_inv,
                                                 generation=cur_gen)
        return curr

    def _get_inventory(self, context, rp_uuid):
        url = '/resource_providers/%s/inventories' % rp_uuid
        result = self.get(url, global_request_id=context.global_id)
        if not result:
            return None
        return result.json()

    def get_provider_tree_and_ensure_root(self, context, rp_uuid, name=None,
                                          parent_provider_uuid=None):
        self._ensure_resource_provider(
            context, rp_uuid, name=name,
            parent_provider_uuid=parent_provider_uuid)
        for uuid in self._provider_tree.get_provider_uuids():
            self._refresh_and_get_inventory(context, uuid)
        # Return a *copy* of the tree.
        return copy.deepcopy(self._provider_tree)

    def ensure_resource_classes(self, context, names):
        """Make sure resource classes exist."""
        version = '1.7'
        to_ensure = set(n for n in names
                        if n.startswith(fields.ResourceClass.CUSTOM_NAMESPACE))

        for name in to_ensure:
            # no payload on the put request
            resp = self.put(
                "/resource_classes/%s" % name, None, version=version,
                global_request_id=context.global_id)
            if not resp:
                msg = ("Failed to ensure resource class record with placement "
                       "API for resource class %(rc_name)s. Got "
                       "%(status_code)d: %(err_text)s.")
                args = {
                    'rc_name': name,
                    'status_code': resp.status_code,
                    'err_text': resp.text,
                }
                LOG.error(msg, args)
                raise exception.InvalidResourceClass(resource_class=name)

    def update_from_provider_tree(self, context, new_tree):
        """Flush changes from a specified ProviderTree back to placement.

        The specified ProviderTree is compared against the local cache.  Any
        changes are flushed back to the placement service.  Upon successful
        completion, the local cache should reflect the specified ProviderTree.

        This method is best-effort and not atomic.  When exceptions are raised,
        it is possible that some of the changes have been flushed back, leaving
        the placement database in an inconsistent state.  This should be
        recoverable through subsequent calls.
        :param context: The security context
        :param new_tree: A ProviderTree instance representing the desired state
                         of providers in placement.
        :raises: ResourceProviderSyncFailed if any errors were encountered
                 attempting to perform the necessary API operations.
        """
        # Helper methods herein will be updating the local cache (this is
        # intentional) so we need to grab up front any data we need to operate
        # on in its "original" form.
        old_tree = self._provider_tree
        old_uuids = old_tree.get_provider_uuids()
        new_uuids = new_tree.get_provider_uuids()

        # Do provider deletion first, since it has the best chance of failing
        # for non-generation-conflict reasons (i.e. allocations).
        uuids_to_remove = set(old_uuids) - set(new_uuids)
        # We have to do deletions in bottom-up order, so we don't error
        # attempting to delete a parent who still has children.
        for uuid in reversed(old_uuids):
            if uuid not in uuids_to_remove:
                continue
            self._delete_provider(uuid)

        # Now create (or load) any "new" providers
        uuids_to_add = set(new_uuids) - set(old_uuids)
        # We have to do additions in top-down order, so we don't error
        # attempting to create a child before its parent exists.
        for uuid in new_uuids:
            if uuid not in uuids_to_add:
                continue
            provider = new_tree.data(uuid)
            self._ensure_resource_provider(
                context, uuid, name=provider.name,
                parent_provider_uuid=provider.parent_uuid)

        # At this point the local cache should have all the same providers as
        # new_tree.  Whether we added them or not, walk through and diff/flush
        # inventories, traits, and aggregates as necessary (the helper methods
        # are set up to check and short out when the relevant property does not
        # differ from what's in the cache).
        # If we encounter any error and remove a provider from the cache, all
        # its descendants are also removed, and set_*_for_provider methods on
        # it wouldn't be able to get started. Walking the tree in bottom-up
        # order ensures we at least try to process all of the providers.
        for uuid in reversed(new_uuids):
            pd = new_tree.data(uuid)
            self._update_inventory(pd.uuid, pd.inventory)

    def _get_providers_in_tree(self, context, uuid):
        """Queries the placement API for a list of the resource providers in
        the tree associated with the specified UUID.
        :param context: The security context
        :param uuid: UUID identifier for the resource provider to look up
        :return: A list of dicts of resource provider information, which may be
                 empty if no provider exists with the specified UUID.
        :raise: ResourceProviderRetrievalFailed on error.
        """
        resp = self.get("/resource_providers?in_tree=%s" % uuid,
                        version=NESTED_PROVIDER_API_VERSION,
                        global_request_id=context.global_id)

        if resp.status_code == 200:
            return resp.json()['resource_providers']

        # Some unexpected error
        placement_req_id = self. get_placement_request_id(resp)
        msg = ("[%(placement_req_id)s] Failed to retrieve resource provider "
               "tree from placement API for UUID %(uuid)s. Got "
               "%(status_code)d: %(err_text)s.")
        args = {
            'uuid': uuid,
            'status_code': resp.status_code,
            'err_text': resp.text,
            'placement_req_id': placement_req_id,
        }
        LOG.error(msg, args)
        raise exception.ResourceProviderRetrievalFailed(uuid=uuid)

    def _delete_provider(self, rp_uuid, global_request_id=None):
        resp = self.delete('/resource_providers/%s' % rp_uuid,
                           global_request_id=global_request_id)
        # Check for 404 since we don't need to warn/raise if we tried to delete
        # something which doesn"t actually exist.
        if resp or resp.status_code == 404:
            if resp:
                LOG.info("Deleted resource provider %s", rp_uuid)
            # clean the caches
            try:
                self._provider_tree.remove(rp_uuid)
            except ValueError:
                pass
            self._association_refresh_time.pop(rp_uuid, None)
            return

        msg = ("[%(placement_req_id)s] Failed to delete resource provider "
               "with UUID %(uuid)s from the placement API. Got "
               "%(status_code)d: %(err_text)s.")
        args = {
            'placement_req_id': self.get_placement_request_id(resp),
            'uuid': rp_uuid,
            'status_code': resp.status_code,
            'err_text': resp.text
        }
        LOG.error(msg, args)
        # On conflict, the caller may wish to delete allocations and
        # redrive.  (Note that this is not the same as a
        # PlacementAPIConflict case.)
        if resp.status_code == 409:
            raise exception.ResourceProviderInUse()
        raise exception.ResourceProviderDeletionFailed(uuid=rp_uuid)