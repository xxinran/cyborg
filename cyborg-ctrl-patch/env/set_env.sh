export OPAE_PLATFORM_ROOT=/home/centos/software
export AOCL_BOARD_PACKAGE_ROOT=/home/centos/software/opencl/opencl_bsp
export INTELFPGAOCLSDKROOT=/root/intelFPGA_pro/18.1/aclrte-linux64
export CL_CONTEXT_COMPILER_MODE_INTELFPGA=3
source $INTELFPGAOCLSDKROOT/init_opencl.sh
source $AOCL_BOARD_PACKAGE_ROOT/linux64/libexec/setup_permissions.sh
source /opt/intel/openvino/bin/setupvars.sh

