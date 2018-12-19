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

from openstack import connection


_CONN = None
_RPT_TPL = "/resource_providers/%s/traits"


def _get_placement():
    global _CONN
    if _CONN is None:
        _CONN = connection.Connection(cloud='devstack-admin')
    return _CONN.placement


def _get_rp_traits(rp_uuid):
    placement = _get_placement()
    resp = placement.get(_RPT_TPL % rp_uuid, microversion='1.6')
    if resp.status_code != 200:
        raise Exception(
            "Failed to get traits for rp %s: HTTP %d: %s" %
            (rp_uuid, resp.status_code, resp.text))
    return resp.json()


def _ensure_traits(trait_names):
    placement = _get_placement()
    for trait in trait_names:
        resp = placement.put('/traits/' + trait, microversion='1.6')
        if resp.status_code == 201:
            print("Created trait %s" % trait)
        elif resp.status_code == 204:
            print("Trait %s already existed" % trait)
        else:
            raise Exception(
                "Failed to create trait %s: HTTP %d: %s" %
                (trait, resp.status_code, resp.text))


def _put_rp_traits(rp_uuid, traits_json):
    placement = _get_placement()
    resp = placement.put(
        _RPT_TPL % rp_uuid, json=traits_json, microversion='1.6')
    if resp.status_code != 200:
        raise Exception(
            "Failed to set traits to %s for rp %s: HTTP %d: %s" %
            (traits_json, rp_uuid, resp.status_code, resp.text))


def add_traits_to_rp(rp_uuid, trait_names):
    _ensure_traits(trait_names)
    traits_json = _get_rp_traits(rp_uuid)
    traits = list(set(traits_json['traits'] + trait_names))
    traits_json['traits'] = traits
    _put_rp_traits(rp_uuid, traits_json)


def delete_traits_with_prefixes(rp_uuid, trait_prefixes):
    traits_json = _get_rp_traits(rp_uuid)
    traits = [
        trait for trait in traits_json['traits']
        if not any(trait.startswith(prefix)
                   for prefix in trait_prefixes)]
    traits_json['traits'] = traits
    _put_rp_traits(rp_uuid, traits_json)
