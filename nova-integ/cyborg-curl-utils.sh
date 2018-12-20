#!/bin/bash

get_resource() {
   local rel_url=$1 # e.g. "device_profiles", "accelerator_requests"

   local token=$(openstack token issue -c id -f value)
   local auth="X-Auth-Token: $token"
   local ctype="Content-Type: application/json"
   curl -s -H "$ctype" -H "$auth" "$CYURL/$rel_url"
}

create_device_profile() {
   # Create a device profile with a given name from a JSON in
   # a file. See create_devprof_json_file() below for example file.
   #
   local f=$1
   local body=$(tr -s '\n' ' ' < "$f")

   local token=$(openstack token issue -c id -f value)
   local auth="X-Auth-Token: $token"
   local ctype="Content-Type: application/json"
   curl -s -H "$ctype" -H "$auth" -X POST -d "$body" \
        $CYURL/device_profiles
}

create_devprof_example_file() {
   local name=$1
   local file="/tmp/_example_dp_json.txt"
   # The '=name=' gets replaced by the real device profile name.
   cat <<EOF > $file
{ "name": \"$name\",
  "groups": [
      { "resources:CUSTOM_ACCELERATOR_XYZ": "2",
        "trait:CUSTOM_TRAIT_NEVER": "forbidden",
        "trait:CUSTOM_TRAIT_ALWAYS": "required"
      },
      { "resources:CUSTOM_ACCELERATOR_ABC": "3",
        "trait:CUSTOM_TRAIT_BAR": "forbidden",
        "trait:CUSTOM_TRAIT_FOO": "required"
      }
  ]
}
EOF
}

create_arq() {
   local devprof_name=$1
   local body="{\"device_profile_name\": \"$devprof_name\"}"

   local token=$(openstack token issue -c id -f value)
   local auth="X-Auth-Token: $token"
   local ctype="Content-Type: application/json"
   curl -s -H "$ctype" -H "$auth" -X POST -d "$body" \
        $CYURL/accelerator_requests
}

bind_arq() {
   local arq_uuid=$1
   local f='/tmp/arq_binding_json.txt'

   cat <<EOF > $f
       {"$arq_uuid": [
           {"path": "/hostname", "op": "add", "value": "pilot"},
           {"path": "/device_rp_uuid", "op": "add",
                  "value": "6026b395-be7b-426f-8baa-ca88279707fd"},
           {"path": "/instance_uuid", "op": "add", "value": "bfaa837d-1ab5-4fd8-90eb-94008f2919ae"}
        ]
      }
EOF
   local body=$(tr -s '\n' ' ' < $f |
                sed -e 's/^[[:space:]]*//;s/[[:space:]]*$//')

   local token=$(openstack token issue -c id -f value)
   local auth="X-Auth-Token: $token"
   local ctype="Content-Type: application/json"
   local atype="Accept: application/json"
   set -x
   curl -s -H "$ctype" -H "$atype" -H "$auth" -X PATCH -d "$body" \
        -w "%{http_code}\n" $CYURL/accelerator_requests
   set +x

   /bin/rm -f $f
}

unbind_arq() {
   local arq_uuid=$1
   local f='/tmp/arq_unbinding_json.txt'

   cat <<EOF > $f
      {"$arq_uuid": [
          {"path": "/hostname", "op": "remove"},
          {"path": "/device_rp_uuid", "op": "remove"},
          {"path": "/instance_uuid", "op": "remove"}
        ]
      }
EOF
   local body=$(cat $f | tr -s '\n' ' ')

   local token=$(openstack token issue -c id -f value)
   local auth="X-Auth-Token: $token"
   local ctype="Content-Type: application/json"
   curl -s -H "$ctype" -H "$auth" -X PATCH -d "$body" \
        -w "%{http_code}\n" $CYURL/accelerator_requests

   /bin/rm -f $f
}

delete_arq() {
   local arq_uuid=$1

   local token=$(openstack token issue -c id -f value)
   local auth="X-Auth-Token: $token"
   local ctype="Content-Type: application/json"
   curl -s -H "$ctype" -H "$auth" -X DELETE \
        $CYURL/accelerator_requests\?arqs="$arq_uuid"
}

source /opt/stack/devstack/openrc admin admin
export CYURL="http://localhost/accelerator/v2"
