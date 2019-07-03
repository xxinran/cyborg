#!/bin/bash

VM_NAME=${1:-c7-1708-2}
echo "Create a VM with name: $VM_NAME"
NET_UUID=a86706f9-9eed-4896-9667-68ea8bcbe63e
NET_NAEM=private
FLOATING_NET=public
# IMAGE_NAME=centos-1708 
IMAGE_NAME=ov2
KEY_NAME=teamkey
# FLAVOR=m1.large
FLAVOR=openvino
FPGA_ENV_FILE=/tmp/set_evn.sh
FPGA_ENV_FILE_DST=/home/centos/demo/set_evn.sh
PROGAM_FPGA_FILE=/tmp/bitstream.sh
PROGAM_FPGA_FILE_DST=/home/centos/demo/bitstream.sh
IP_CAM_DEMO_FILE=/tmp/run.ip.demo
IP_CAM_DEMO_FILE_DST=/home/centos/demo/run.ip.demo

IP_PRE_SET=172.24.4.216
FIP=`openstack floating ip list --floating-ip-address $IP_PRE_SET -c "Floating IP Address"`
if [ -z "$FIP" ]; then
    openstack floating ip create --floating-ip-address $IP_PRE_SET $FLOATING_NET
fi
IP_PRE_SET=172.24.4.96
FIP=`openstack floating ip list --floating-ip-address $IP_PRE_SET -c "Floating IP Address"`
if [ -z "$FIP" ]; then
    openstack floating ip create --floating-ip-address $IP_PRE_SET $FLOATING_NET
fi

FIP=`openstack floating ip list --status DOWN -c "Floating IP Address" -f value |tail -n 1`
if [ -z "$FIP" ]; then
    echo "Do not find a floating ip, create a new one"
    openstack floating ip create $FLOATING_NET
    # openstack server remove floating ip $VM_NAME
fi

CLOUD_INIT=/tmp/cloud-init.cfg

cat > $CLOUD_INIT <<<'#cloud-config
ssh_pwauth: True
password: 123456
chpasswd:
  list: |
    centos:123456
    root:123456
  expire: False'

INIT_SCRIPT=/tmp/cloud-init.sh
cat > $INIT_SCRIPT <<<'#!/bin/bash
service sshd stop
passwd root << EOF
123456
123456
EOF
useradd -m centos
useradd -m user
passwd centos << EOF
123456
123456
EOF
passwd user << EOF
123456
123456
EOF
touch /home/user/test.sh
service sshd start
echo "PermitRootLogin yes" | sudo tee -a /etc/ssh/sshd_config
echo "UsePAM yes" | sudo tee -a /etc/ssh/sshd_config
echo "PasswordAuthentication yes" | sudo tee -a /etc/ssh/sshd_config
service sshd restart'


cat > $IP_CAM_DEMO_FILE <<< 'UDER=admin
PASS=Maxiaoha123
CHANNEL=${1:-3}
ADDR=${2:-192.168.0.150}
VIDEO_FILE="/home/centos/software/obama.mp4"
VIDEO_FILE=rtsp://$UDER:$PASS@$ADDR/Streaming/Channels/$CHANNEL
CMD="/root/inference_engine_samples_build/intel64/Release/interactive_face_detection_demo -m=/opt/intel/openvino/deployment_tools/intel_models/face-detection-retail-0004/FP32/face-detection-retail-0004.xml -m_ag=/opt/intel/openvino/deployment_tools/intel_models/age-gender-recognition-retail-0013/FP32/age-gender-recognition-retail-0013.xml  -m_hp=/opt/intel/openvino/deployment_tools/intel_models/head-pose-estimation-adas-0001/FP32/head-pose-estimation-adas-0001.xml -m_em=/opt/intel/openvino/deployment_tools/intel_models/emotions-recognition-retail-0003/FP32/emotions-recognition-retail-0003.xml -d HETERO:FPGA,CPU -d_ag HETERO:FPGA,CPU -d_em HETERO:FPGA,CPU -d_hp HETERO:FPGA,CPU  -n_ag=1 -n_em=1 -i $VIDEO_FILE"
$CMD'  

echo "aocl program acl0 /opt/intel/openvino/bitstreams/a10_dcp_bitstreams/2019R1_RC_FP11_ResNet_SqueezeNet_VGG.aocx" > $PROGAM_FPGA_FILE

cat > $FPGA_ENV_FILE <<<'
export OPAE_PLATFORM_ROOT=/home/centos/software
export AOCL_BOARD_PACKAGE_ROOT=/home/centos/software/opencl/opencl_bsp
export INTELFPGAOCLSDKROOT=/root/intelFPGA_pro/18.1/aclrte-linux64
export CL_CONTEXT_COMPILER_MODE_INTELFPGA=3
source $INTELFPGAOCLSDKROOT/init_opencl.sh
source $AOCL_BOARD_PACKAGE_ROOT/linux64/libexec/setup_permissions.sh
source /opt/intel/openvino/bin/setupvars.sh'


# No pci pass through
# openstack server create --key-name $KEY_NAME --user-data $INIT_SCRIPT --user-data $CLOUD_INIT --image $IMAGE_NAME --flavor $FLAVOR --nic net-id=$NET_UUID $VM_NAME 
openstack server create --config-drive true  --key-name $KEY_NAME --user-data $INIT_SCRIPT --user-data $CLOUD_INIT --image $IMAGE_NAME --flavor $FLAVOR --network $NET_NAEM --file $FPGA_ENV_FILE_DST=$FPGA_ENV_FILE --file $PROGAM_FPGA_FILE_DST=$PROGAM_FPGA_FILE --file $IP_CAM_DEMO_FILE_DST=$IP_CAM_DEMO_FILE $VM_NAME 

openstack server list
sleep 5 
# https://stackoverflow.com/questions/12204192/awk-multiple-delimiter
VMIP=`openstack server show $VM_NAME -c addresses -f value |awk -F=" |," '{print $2}'`
# https://stackoverflow.com/questions/369758/how-to-trim-whitespace-from-a-bash-variable
# remove leading whitespace characters
VMIP="${VMIP#"${VMIP%%[![:space:]]*}"}"
# remove trailing whitespace characters
VMIP="${VMIP%"${VMIP##*[![:space:]]}"}"
NETNS=`ip netns |grep qrouter | awk '{print $1}'`
FIP=`openstack floating ip list --status DOWN -c "Floating IP Address" -f value |head -n 1`
# FIP=`openstack floating ip list --status DOWN -c "Floating IP Address" -f value |tail -n 1`
echo "Attach $FIP to VM: $VM_NAME"
openstack server add floating ip $VM_NAME $FIP
echo "Need to remove log info: "
echo "    ssh-keygen -f \"/home/cloud/.ssh/known_hosts\" -R $FIP"
ssh-keygen -f "/home/cloud/.ssh/known_hosts" -R $FIP
openstack server list
echo "openstack server add floating ip $VM_NAME $FIP"
echo "openstack server list"
echo "openstack console log show $VM_NAME"
echo "ssh centos@$FIP"
echo "sudo ip netns exec $NETNS ssh centos@$VMIP"
