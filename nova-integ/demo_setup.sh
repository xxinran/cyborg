#!/bin/bash

# This script assumes a devstack all-in-1 environment, where the
# current host is both a controller and a compute node.

# This script sets up a single fake device in Cyborg db, creates
# some example device profiles and populates Placement with
# RPs, RCs and traits for that device.

# Program a single bitstream. Nothing else.

def_vars() {
   rc='CUSTOM_ACCELERATOR_FPGA'
   rp_name='FPGA_Intel_PAC_Arria10_1'
   device_trait="CUSTOM_FPGA_INTEL_PAC_ARRIA10"
   openstack='openstack --os-placement-api-version 1.17'
   demo_file="/tmp/demo_file.txt" # temp file to store created flavor names

   region_type_id='9926AB6D6C925A68AABCA7D84C545738'
   region_trait="CUSTOM_REGION_${region_type_id}"

   # genomics_fn_id="18B79FFA2EE54AA096EF4230DAFACB5F"
   # genomics_fn_trait="CUSTOM_FUNCTION_ID_$genomics_fn_id"
   nlb0_fn_id="D8424DC4A4A3C413F89E433683F9040B"
   nlb3_fn_id="F7DF405CBD7ACF7222F144B0B93ACD18"
}

set_image_properties() {
    echo Setting image properties
    openstack image set --property \
        "accel:function_id=${nlb0_fn_id}" nlb-0.gbs
    openstack image set --property \
        "accel:region_type_id=${region_type_id}" nlb-0.gbs
    openstack image set --property \
        "accel:function_id=${nlb3_fn_id}" nlb-3.gbs
    openstack image set --property \
        "accel:region_type_id=${region_type_id}" nlb-3.gbs
}

setup_placement() {
   echo "Creating custom RC $rc"
   $openstack resource class create $rc

   echo "Creating traits"
   echo "    $device_trait $region_trait"
   $openstack trait create $device_trait
   $openstack trait create $region_trait
   # $openstack trait create $genomics_fn_trait

   echo "Getting compute node RP"
   # Assumes that current node is the compute node, as in devstack env
   local cn_uuid=$($openstack resource provider list --name $HOSTNAME \
                   -c uuid -f value)
   [[ "$cn_uuid" == "" ]] && echo Could not get compute node RP && return 1
   echo "   Compute node UUID: " $cn_uuid

   echo "Creating device RP nested under compute node RP"
   # This is a global var that will be later passed to setup_db
   devrp_uuid=$($openstack resource provider create $rp_name \
                       --parent-provider $cn_uuid -c uuid -f value)
   [[ "$devrp_uuid" == "" ]] && echo Could not create device RP && return 1
   echo "   Device RP UUID: " $devrp_uuid

   echo "Applying traits to the device RP:"
   echo "   " $device_trait $region_trait
   $openstack resource provider trait set $devrp_uuid \
       --trait $device_trait --trait $region_trait > /dev/null

   echo "Populating inventory for device RP"
   $openstack resource provider inventory set $devrp_uuid \
       --resource $rc=1 --resource $rc:max_unit=1 > /dev/null
}


setup_db() {
   local device_rp_uuid="$1"
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
   INSERT INTO deployables
      (uuid, num_accelerators, name, device_id, rp_uuid, driver_name)
      SELECT '6026b395-be7b-426f-8baa-ca88279707fd', 1, 'Arria10', id,
         "$device_rp_uuid", 'intel' FROM devices WHERE type = 'FPGA';
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

   echo "Populating Cyborg database"
   mysql -u root -e "$(cat $TMP_SCRIPT)"
   /bin/rm -f $TMP_SCRIPT $TMP_PCI
}

create_flavor() {
    local name=$1
    local devprof_name=$2
    echo Creating flavor named $name
    openstack flavor create --vcpus 2 --ram 4096 --disk 10 \
        --property "accel:device_profile=$devprof_name" $name > /dev/null
    echo $name >> $demo_file
}

create_fpga_aas_dp_flavor() {
    local name=$1
    local region_trait=$2

    local img_name="${name}.gbs"
    local dp_name="${name}-fpga-aas-dp"
    local flavor_name="${name}-fpga-aas-flavor"

    local bitstream_id=$(openstack image list --name ${img_name} -c ID -f value)
    local dp_file="/tmp/_junk.txt"

    [[ "$bitstream_id" == "" ]] && \
       echo Image $name does not exist && exit 1

    cat <<EOF > $dp_file
{ "name": "$dp_name",
    "groups": [
        {"resources:CUSTOM_ACCELERATOR_FPGA": "1",
         "trait:$region_trait": "required",
         "accel:bitstream_id": "$bitstream_id"
        }
    ]
}
EOF

    echo Creating device profile named $dp_name
    create_device_profile "$dp_file" > /dev/null
    /bin/rm -f $dp_file

    create_flavor $flavor_name $dp_name
}

create_af_aas_dp_flavor() {
    local name=$1
    local device_trait=$2
    local function_id=$3

    local dp_name="${name}-afaas-dp"
    local flavor_name="${name}-afaas-flavor"

    local dp_file="/tmp/_junk.txt"

    cat <<EOF > $dp_file
{ "name": "$dp_name",
    "groups": [
        {"resources:CUSTOM_ACCELERATOR_FPGA": "1",
         "trait:$device_trait": "required",
         "accel:function_id": "$function_id"
        }
    ]
}
EOF

    echo Creating device profile named $dp_name
    create_device_profile "$dp_file" > /dev/null
    /bin/rm -f $dp_file

    create_flavor $flavor_name $dp_name
}

setup_device_profiles_and_flavors() {
   source ./cyborg-curl-utils.sh

   create_fpga_aas_dp_flavor "nlb-0" "$region_trait"
   create_fpga_aas_dp_flavor "nlb-3" "$region_trait"
   create_af_aas_dp_flavor "nlb-0" "$device_trait" "$nlb0_fn_id"
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

delete_flavors() {
   [[ -f $demo_file ]] && \
       openstack flavor delete $(cat $demo_file)
   # device profiles will get deleted when we delete db
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
[[ "$1" == "-d" ]] && DELETE=1

def_vars
if [[ "$DELETE" -eq 0 ]]; then
   cat /dev/null > $demo_file
   devrp_uuid=''
   set_image_properties
   setup_placement
   setup_db $devrp_uuid
   setup_device_profiles_and_flavors
else
   echo Deleting flavors, Cyborg db entries and Placement RPs/RCs
   delete_flavors
   delete_db
   teardown_placement
   /bin/rm -f $demo_file
fi
