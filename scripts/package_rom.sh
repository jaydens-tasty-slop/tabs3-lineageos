#!/usr/bin/env bash
# Resume the OTA target using the existing Android output and Ninja graph.
set -eo pipefail
rm -f /workspace/state/build-rom.exit
source /workspace/scripts/build_env.sh
m -j8 otapackage
# Match Lineage's naming rule without invoking the default full build goal.
package_dir=$(get_build_var PRODUCT_OUT)
package_version=$(get_build_var LINEAGE_VERSION)
cp -f "$package_dir/obj/PACKAGING/system_intermediates/system.img" "$package_dir/system.img"
ln -f "$package_dir/lineage_gts3lwifi-ota.zip" "$package_dir/lineage-$package_version.zip"
sha256sum "$package_dir/lineage-$package_version.zip" \
    | sed "s|$package_dir/||" > "$package_dir/lineage-$package_version.zip.sha256sum"
