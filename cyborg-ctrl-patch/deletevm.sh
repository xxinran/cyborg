#!/bin/bash

VM_NAME=${1:-c7-1708-2}
echo "Delete VM with name: $VM_NAME"
NET_UUID=a86706f9-9eed-4896-9667-68ea8bcbe63e
NET_NAEM=private
FLOATING_NET=public
IMAGE_NAME=centos-1708 
KEY_NAME=teamkey
FLAVOR=m1.large
FIP=`openstack floating ip list --status DOWN -c "Floating IP Address" -f value |tail -n 1`

AUTH="X-Auth-Token: $(openstack token issue -c id -f value)"
CTYPE="Content-Type: application/json"
CYURL=`openstack endpoint list --service cyborg --interface "public" -c "URL" -f value`
VM_UUID=`openstack server list --name $VM_NAME -c ID -f value`

# delete VM
openstack server delete $VM_NAME

ARQ_UUID=$(curl -s -H "$CTYPE" -H "$AUTH" "$CYURL/accelerator_requests?bind_state=resolved&instance=$VM_UUID" | grep '"uuid": ".*?"' -oP |awk -F='"|:| ' '{print $3}')
echo "Find accelerator requests uuid: $ARQ_UUID"
ARQ_UUID=${ARQ_UUID##\"}
ARQ_UUID=${ARQ_UUID%%\"}

# unbind arq
BODY="{\"$ARQ_UUID\": [
    {\"path\": \"/hostname\", \"op\": \"remove\"},
    {\"path\": \"/device_rp_uuid\", \"op\": \"remove\"},
    {\"path\": \"/instance_uuid\", \"op\": \"remove\"}
  ]
}"
echo $BODY
echo $ARQ_UUID
curl -s -H "$CTYPE" -H "$AUTH" -X PATCH -d "$BODY" -w "%{http_code}\n" $CYURL/accelerator_requests

# delete arq
curl -s -H "$CTYPE" -H "$AUTH" -X DELETE  $CYURL/accelerator_requests\?arqs="$ARQ_UUID"

sleep 3
openstack server list
