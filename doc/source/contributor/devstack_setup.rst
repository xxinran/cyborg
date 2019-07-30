====================
DevStack Quick Start
====================

.. note::

   Because OPAE packages depend on libjson0, which is not available
   after Ubuntu 16.04, so cyborg can't be installed on Ubuntu
   higher than 16.04 now.

Create stack user (optional)
----------------------------

Devstack should be run as a non-root user with sudo enabled (standard logins to
cloud images such as “ubuntu” or “cloud-user” are usually fine).

You can quickly create a separate stack user to run DevStack with.

.. code-block:: console

   $ sudo useradd -s /bin/bash -d /opt/stack -m stack

Since this user will be making many changes to your system, it should have sudo
privileges:

.. code-block:: console

   $ echo "stack ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/stack

.. code-block:: console

   $ sudo su - stack

Download DevStack
-----------------

.. code-block:: console

   $ git clone https://opendev.org/openstack/devstack

.. code-block:: console

   $ cd devstack

The `devstack` repo contains a script that installs OpenStack.

Create local.conf file
----------------------

Create a `local.conf` file at the root of the devstack git repo.

Host settings
>>>>>>>>>>>>>

::

  [[local|localrc]]
  # Multi-host settings
  MULTI_HOST=False
  HOST_IP=YOUR_IP_CONFIG
  SERVICE_HOST=$HOST_IP
  DATABASE_TYPE=mysql
  MYSQL_HOST=$HOST_IP
  RABBIT_HOST=$HOST_IP

- Replace YOUR_IP_CONFIG with your host IP (e.g. 10.0.0.72 or localhost).
- If you are not configuring OpenStack env in multi-host settings, please set
  MULTI_HOST=False.

Password settings
>>>>>>>>>>>>>>>>>

::

  # Passwords
  DATABASE_PASSWORD=123
  ADMIN_PASSWORD=123
  MYSQL_PASSWORD=123
  RABBIT_PASSWORD=123
  SERVICE_PASSWORD=123
  SERVICE_TOKEN=ADMIN

- Pre-set the passwords to prevent interactive prompts.

Enable services
>>>>>>>>>>>>>>>

::

  #FIXED_RANGE=192.168.128.0/24
  #IPV4_ADDRS_SAFE_TO_USE=192.168.128.0/24
  #GIT_BASE=/opt/git
  disable_service n-net
  disable_service tempest
  disable_service heat
  enable_service q-svc
  enable_service q-agt
  enable_service q-dhcp
  enable_service q-l3
  enable_service q-meta
  enable_service neutron
  enable_service n-novnc
  enable_plugin cyborg https://opendev.org/openstack/cyborg
  NOVA_VNC_ENABLED=True
  NOVNCPROXY_URL="http://$SERVICE_HOST:6080/vnc_auto.html"
  VNCSERVER_LISTEN=0.0.0.0
  VNCSERVER_PROXYCLIENT_ADDRESS=$SERVICE_HOST
  RECLONE=False
  #enable Logging
  LOGFILE=/opt/stack/logs/stack.sh.log
  VERBOSE=True
  LOG_COLOR=True
  LOGDIR=/opt/stack/logs

- Uncomment GIT_BASE configuration if you have a local git repo

- enable_plugin cyborg will execute cyborg/devstack/plugin.sh and start cyborg
  service

- The devstack logs will appear in $LOGDIR

.. note::

  If you got version conflicts, please set `PIP_UPGRADE` to `True` in local.conf

Disable OPAE install
>>>>>>>>>>>>>>>>>>>>

::

  OPAE_INSTALL_ENABLE=false

- By default OPAE_INSTALL_ENABLE is True.

- You need to set OPAE_INSTALL_ENABLE as false explicitly,
  if not need OPEA enviroment.

- At present OPAE depends on OS verson heavily.

.. note::

  If you do not want to try Intel FPGA, you can disable OPAE install. Then you
  do not depend on specific OS verson.

Multi-Node Lab
--------------
If you want to setup an OpenStack with cyborg in a realistic test configuration
with multiple physical servers. Please ref [#MultiNodeLab]_.

Cluster Controller
>>>>>>>>>>>>>>>>>>

::

  disable_service cyborg-agent

Compute Nodes
>>>>>>>>>>>>>

::

  enable_service cyborg-agent
  disable_service cyborg-api
  disable_service cyborg-cond

- If you do not want to setup cyborg-agent on controller, you can disable it.
- You do not need to enable cyborg-api and cyborg-cond on compute nodes.

Cell V2 Deployment
>>>>>>>>>>>>>>>>>>

Compute node services must be mapped to a cell before they can be used.
Cell V2 deployment, please ref [#CellV2]_.

After each compute node is stacked, verify it shows up in the
**nova service-list --binary nova-compute** output. The compute service is
registered in the cell database asynchronously so this may require polling.

Once the compute node services shows up, run the **./tools/discover_hosts.sh**
script from the control node to map compute hosts to the single cell. You can
also simply run these 2 comands on the controller,
**nova-manage cell_v2 discover_hosts --verbose** and
**nova-manage cell_v2 simple_cell_setup**.

The compute service running on the primary control node will be discovered
automatically when the control node is stacked so this really only needs to
be performed for subnodes.

Run DevStack
------------

.. code-block:: console

   $ ./stack.sh

This will take a 30-40 minutes, largely depending on the speed of your internet
connection. Many git trees and packages will be installed during this process.

It will speed up your installation if you have a local GIT_BASE.

Use OpenStack
-------------

Command line
>>>>>>>>>>>>

You can `source openrc YOUR_USER YOUR_USER (e.g. source openrc admin admin)` in
your shell, and then use the `openstack` command line tool to manage your
devstack.

Horizon
>>>>>>>

You can access horizon to experience the web interface to OpenStack, and manage
vms, networks, volumes, and images from there.

References
==========

.. [#MultiNodeLab] `Openstack Multi-Node Lab Setup
  <https://docs.openstack.org/devstack/latest/guides/multinode-lab.html>`_
.. [#CellV2] `Openstack Cell V2 Deployment Guide
  <https://docs.openstack.org/nova/latest/user/cells.html>`_
