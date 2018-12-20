#!/bin/python

"""
  Test program to validate the Cyborg client.
"""

import sys
from cyborgclient.v2 import client


class MyClient(object):
    @staticmethod
    def list_device_profiles(cyborg, name=None):
        dp = cyborg.nova_device_profiles.list(name=name)
        print 'dp: ', dp

    @staticmethod
    def get_device_profile(cyborg, name):
        dp = cyborg.nova_device_profiles.list(name=name)
        print 'dp: ', dp

    @staticmethod
    def list_arqs(cyborg, name=None):
        arqs = cyborg.arqs.list()
        print 'arqs: ', arqs

    @staticmethod
    def create_arqs(cyborg, device_profile_name):
        arqs = cyborg.arqs.create(device_profile_name=device_profile_name)
        print 'arqs: ', arqs

    @staticmethod
    def delete_arq(cyborg, uuid):
        arqs = cyborg.arqs.delete(arqs=uuid)
        print 'arqs: ', arqs

    @staticmethod
    def delete_all_arqs(cyborg, dummy):
        arqs = cyborg.arqs.list()
        for arq in arqs:
            print 'Deleting ARQ', arq.uuid
            MyClient.delete_arq(cyborg, arq.uuid)

    @staticmethod
    def get_resolved_arqs(cyborg, instance):
        try:
            arqs = cyborg.arqs.get_resolved_arqs_for_instance(instance)
            print 'arqs: ', arqs
        except Exception as e:
            print e

    @staticmethod
    def bind_arq(cyborg, arq_uuid):
        import os
        uuid = '48a9d0ec-9f06-4094-9d49-8c4395fdcc00'
        binding = {"arq_uuid": arq_uuid,
                   "host_name": os.environ['HOSTNAME'],
                   "device_rp_uuid": uuid,
                   "instance_uuid": uuid
                   }
        bindings = [binding]
        cyborg.arq_bindings.create(bindings=bindings)

    @staticmethod
    def unbind_arq(cyborg, arq_uuid):
        cyborg.arq_bindings.delete(arqs=arq_uuid)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print 'Usage: cyclient.py <method> <arg>'
        sys.exit(-1)

    cyborg = client.Client()
    funcname = sys.argv[1]
    arg = sys.argv[2]

    m = globals()['MyClient']
    func = getattr(m, funcname)
    print 'Running:', funcname, '(cyborg, \"', arg, '\")'
    # import remote_pdb; remote_pdb.set_trace(port=5959)
    func(cyborg, arg)
