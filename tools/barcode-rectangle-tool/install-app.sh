#!/bin/zsh
set -euo pipefail
script_dir="${0:A:h}"
app_path="$script_dir/Barcode Rectangle Tool.app"
installed_path="/Applications/Barcode Rectangle Tool.app"
registration_tool="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"

"$script_dir/build-app.sh"
ditto "$app_path" "$installed_path"
"$registration_tool" -f "$installed_path"
print "Installed and registered: $installed_path"
