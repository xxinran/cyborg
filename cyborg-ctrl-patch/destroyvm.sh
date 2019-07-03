#!/bin/bash

# MWC password Hk6z4JFe-wyn-u-

# step 0 init some variable
AUTH="X-Auth-Token: $(openstack token issue -c id -f value)"
CTYPE="Content-Type: application/json"
CYURL=`openstack endpoint list --service cyborg --interface "public" -c "URL" -f value`
APIV="OpenStack-API-Version: placement 1.32"


# step 1 list show the FPGA resource
openstack resource provider list
PR_UUID=`openstack resource provider list -f value |grep intel-fpga-dev |head -n 1 |awk '{print $1}'`
OS_PLACEMENT_API_VERSION=1.18 openstack resource provider trait list $PR_UUID

# step 2 list bitstream in glance
BS_FUN_ID=D8424DC4A4A3C413F89E433683F9040B
openstack image list --tag FPGA --property accel:function_id="$BS_FUN_ID"

# step 5 create a VM
VM_NAME=fpga_test
# openstack server create --image cirros-0.4.0-x86_64-disk --flavor $FLAVOR_NAME --nic net-id=private $VM_NAME
# FIP=`openstack floating ip list --status DOWN -c "Floating IP Address" -f value |tail -n 1`
# openstack server add floating ip $VM_NAME $FIP
# 
# ssh-keygen -f "/home/cloud/.ssh/known_hosts" -R $FIP
# openstack server list
# COMSUMER=`openstack server list  -c ID -f value --instance-name $VM_NAME |head -n 1`
# openstack console log show $VM_NAME |grep password
# ssh cirros@$FIP
# lspci |grep 09c4
openstack server delete $VM_NAME


# step 4 create a flavor
FLAVOR_NAME=program_bts_id_1
# openstack flavor create --vcpus 2 --ram 4096 --disk 10 \
#     --property "accel:device_profile=$DEVPROF_NAME" $FLAVOR_NAME
openstack flavor delete $FLAVOR_NAME


# step 3 create serveral device profiles
ARRAY=`OS_PLACEMENT_API_VERSION=1.18 openstack resource provider trait list $PR_UUID -c name -f value`
DEVICE_TRAIT=`head -n 1 <<< $ARRAY`
FN_TRAIT=`tail -n 1 <<< $ARRAY`

DEVPROF_NAME=adaas_example
BODY="{ \"name\": \"$DEVPROF_NAME\",
  \"groups\": [
      {\"resources:CUSTOM_ACCELERATOR_FPGA\": \"1\",
       \"trait:$DEVICE_TRAIT\": \"required\"
      }
  ]
}"

DEVPROF_NAME=afaas_example
BODY="{ \"name\": \"$DEVPROF_NAME\",
  \"groups\": [
      {\"resources:CUSTOM_ACCELERATOR_FPGA\": \"1\",
       \"trait:$DEVICE_TRAIT\": \"required\",
       \"trait:$FN_TRAIT\": \"required\"
      }
  ]
}"

DEVPROF_NAME=afaas_example_dyn
BODY="{ \"name\": \"$DEVPROF_NAME\",
  \"groups\": [
      {\"resources:CUSTOM_ACCELERATOR_FPGA\": \"1\",
       \"trait:$DEVICE_TRAIT\": \"required\",
       \"accel:function_id\": \"$BS_FUN_ID\"
      }
  ]
}"

curl -s -H "$CTYPE" -H "$AUTH" -X DELETE $CYURL/device_profiles/$DEVPROF_NAME

# /tmp/tmpjprp5vfa-ascii.cast

