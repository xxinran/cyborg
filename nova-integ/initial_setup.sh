#!/bin/bash

# This script assumes a devstack all-in-1 environment, where the
# current host is both a controller and a compute node.

# This script sets up a single fake device in Cyborg db, creates
# some example device profiles and populates Placement with
# RPs, RCs and traits for that device.

setup_db() {
   local TMP_PCI="/tmp/pci.txt"

   cat <<EOF > $TMP_PCI
   { "domain": "0", "bus": "1", "device": "0", "function": "0" }
EOF
   
   local pci_fn=\'`cat $TMP_PCI`\'
   local hostname=\'$HOSTNAME\'

   # Simple db setup with only one row in each table
   local TMP_SCRIPT="/tmp/setup-db.txt"
   cat <<EOF > $TMP_SCRIPT
   use cyborg;
   DELETE FROM device_profiles;
   DELETE FROM attach_handles;
   DELETE FROM controlpath_ids;
   DELETE FROM deployables;
   DELETE FROM devices;
   INSERT INTO devices (type,vendor,model,hostname, uuid)
      VALUES ('FPGA', 'Intel', 'PAC Arria 10', $hostname,
              '38f005dd-7754-4c89-aa84-149b55691d54');
   INSERT INTO deployables (uuid, num_accelerators, name, device_id)
      SELECT '6026b395-be7b-426f-8baa-ca88279707fd', 1, 'Arria10',
             id FROM devices WHERE type = 'FPGA';
   INSERT INTO controlpath_ids (cpid_type, cpid_info, uuid, device_id)
      SELECT 'PCI', $pci_fn, 'd1955566-3de7-441b-bdf2-f22b6a56e58f',
             id FROM devices WHERE type = 'FPGA';
   INSERT INTO attach_handles (attach_type, attach_info, uuid, 
                               deployable_id, cpid_id)
      SELECT 'PCI', $pci_fn, '8194f2c2-6bae-4a93-8feb-6dc3534b875c',
          deployables.id, controlpath_ids.id
      FROM
          deployables, controlpath_ids
      WHERE
          deployables.name = 'Arria10' AND controlpath_ids.cpid_type = 'PCI';

EOF

   mysql -u root -e "$(cat $TMP_SCRIPT)"
   /bin/rm -f $TMP_SCRIPT $TMP_PCI
}

def_vars() {
   rc='CUSTOM_ACCELERATOR_FPGA'
   rp_name='FPGA_Intel_PAC_Arria10_1'
   device_trait="CUSTOM_FPGA_INTEL_PAC_ARRIA10"
   #trait2="CUSTOM_FUNCTION_ID_18B79FFA2EE54AA096EF4230DAFACB5F"
   fn_trait="CUSTOM_FUNCTION_ID_3AFB"
   openstack='openstack --os-placement-api-version 1.17'
}

setup_device_profiles() {
   def_vars
   source ./cyborg-curl-utils.sh
   local dp_file="/tmp/accelerated_function_as_a_service.txt"

   cat <<EOF > $dp_file
   { "name": "afaas_example_1",
     "groups": [
         {"resources:CUSTOM_ACCELERATOR_FPGA": "1",
          "trait:$device_trait": "required",
          "trait:$fn_trait": "required"
         }
     ]
   }
EOF

   create_device_profile $dp_file
   openstack flavor set m1.tiny \
       --property "accel:device_profile=afaas_example_1"

   /bin/rm -f $dp_file
}

setup_placement() {
   def_vars

   echo "Create custom RC"
   $openstack resource class create $rc

   echo "Create traits"
   $openstack trait create $device_trait
   $openstack trait create $fn_trait

   echo "Get compute node RP"
   # Assumes that current node is the compute node, as in devstack env
   local cn_uuid=$($openstack resource provider list --name $HOSTNAME \
                   -c uuid -f value)
   [[ "$cn_uuid" == "" ]] && echo Could not get compute node RP && return 1
   echo "   Compute node UUID: " $cn_uuid

   echo "Create device RP"
   local devrp_uuid=$($openstack resource provider create $rp_name \
                       --parent-provider $cn_uuid -c uuid -f value)
   [[ "$devrp_uuid" == "" ]] && echo Could not create device RP && return 1
   echo "Device RP UUID: " $devrp_uuid

   echo "Apply traits to the device RP"
   $openstack resource provider trait set $devrp_uuid \
             --trait $device_trait --trait $fn_trait

   echo "Populate inventory for device RP"
   $openstack resource provider inventory set $devrp_uuid --resource $rc=1
}

delete_db() {
   local TMP_SCRIPT="/tmp/setup-db.txt"
   cat <<EOF > $TMP_SCRIPT
   use cyborg;
   DELETE FROM extended_accelerator_requests;
   DELETE FROM device_profiles;
   DELETE FROM attach_handles;
   DELETE FROM controlpath_ids;
   DELETE FROM deployables;
   DELETE FROM devices;
EOF

   mysql -u root -e "$(cat $TMP_SCRIPT)"
   /bin/rm -f $TMP_SCRIPT
}

teardown_placement() {
   def_vars
   local devrp_uuid=$($openstack resource provider list --name $rp_name \
                      -c uuid -f value)
   $openstack resource provider delete $devrp_uuid

   $openstack resource class delete $rc
}

#### Main
DELETE=0
[[ "$1" == "-d" ]] && echo Deleting db and Placement inventory && DELETE=1

if [[ "$DELETE" -eq 0 ]]; then
   setup_db
   setup_device_profiles
   setup_placement
else
   teardown_placement
   delete_db
fi
