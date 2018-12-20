Run the initial-setup.sh script first before trying out the
Cyborg - Nova integration.

The cyborg-curl-utils.sh script provides some functions to create
device profiles, ARQs and ARQ bindings. These can be useful till
the Cyborg client is in shape.

Example usage::

  $ source cyborg-curl-utils.sh

  # See all device profiles
  $ curl $CYURL/device_profiles

  # Create an ARQ given a device profile name
  $ create_arq "afaas_example.1"

  # Bind an ARQ to a host. This binds to current host as compute node.
  $ bind_arq "09723cbb-c470-4958-baf0-cbcfb91e0f9d"

  # Check that the ARQ's state is 'Bound', hostname is set, etc.
  $ curl $CYURL/arqs

  # API used by Nova to check if all ARQs for an instance are bound
  $ curl $CYURL/arqs?state=resolved\&instance= \
        "bfaa837d-1ab5-4fd8-90eb-94008f2919ae"
