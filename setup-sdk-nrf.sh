#!/bin/sh

# https://tecadmin.net/how-to-identify-a-bash-script-is-sourced-or-executed-directly/
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "Error: This script uses 'export' to set up the environment."
    echo "  └─ Use 'source' instead of executing the script directly."
    exit 1
fi

echo "Setting up toolchain paths."

# SDK/toolchain for sdk-nrf 3.1.1
ncs_install_dir="${ncs_install_dir:-/opt/nordic/ncs}"
ncs_bin_version="${ncs_bin_version:-561dce9adf}"

paths=(
    $ncs_install_dir/toolchains/$ncs_bin_version/bin
    $ncs_install_dir/toolchains/$ncs_bin_version/opt/nanopb/generator-bin
)

# required if dependencies are not installed, see also
# https://docs.zephyrproject.org/latest/develop/getting_started/index.html#install-dependencies
# e.g., "Ninja"
for entry in ${paths[@]}; do
    export PATH=$PATH:$entry
done

export NRFUTIL_HOME=$ncs_install_dir/toolchains/$ncs_bin_version/nrfutil/home
export ZEPHYR_TOOLCHAIN_VARIANT=zephyr
export ZEPHYR_SDK_INSTALL_DIR=$ncs_install_dir/toolchains/$ncs_bin_version/opt/zephyr-sdk
