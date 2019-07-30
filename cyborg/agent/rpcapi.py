# -*- coding: utf-8 -*-

#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Client side of the conductor RPC API."""

from oslo_config import cfg
import oslo_messaging as messaging

from cyborg.common import constants
from cyborg.common import rpc
from cyborg.objects import base as objects_base
from cyborg import objects

from oslo_log import log

LOG = log.getLogger(__name__)


CONF = cfg.CONF


class AgentAPI(object):
    """Client side of the Agent RPC API.

    API version history:

    |    1.0 - Initial version.

    """

    RPC_API_VERSION = '1.0'

    def __init__(self, topic=None):
        super(AgentAPI, self).__init__()
        self.topic = topic or constants.AGENT_TOPIC
        target = messaging.Target(topic=self.topic,
                                  version='1.0')
        serializer = objects_base.CyborgObjectSerializer()
        self.client = rpc.get_client(target,
                                     version_cap=self.RPC_API_VERSION,
                                     serializer=serializer)

    def hardware_list(self, context, values):
        """Signal the agent to find local hardware."""
        pass

    def program_fpga_with_bitstream(self,
                                    context,
                                    deployable_uuid,
                                    bitstream_uuid):
        """Actiion to program a target FPGA"""
        version = '1.0'

        dpl_get = objects.Deployable.get(context, deployable_uuid)
        if not dpl_get:
            # TODO (Li Liu) throw an exception here
            return 0

        cctxt = self.client.prepare(server=dpl_get.host, version=version)
        return cctxt.call(context, 'fpga_program',
                          deployable_uuid=deployable_uuid,
                          image_uuid=bitstream_uuid)

    def fpga_program_v2(self, context, hostname, controlpath_id,
                        bitstream_uuid, driver_name):
        LOG.info('Agent fpga_program_v2: hostname: (%s) ' +
                 'bitstream_id: (%s)', hostname, bitstream_uuid)
        version = '1.0'
        cctxt = self.client.prepare(server=hostname, version=version)
        return cctxt.call(context, 'fpga_program_v2',
                          controlpath_id=controlpath_id,
                          bitstream_uuid=bitstream_uuid,
                          driver_name=driver_name)
