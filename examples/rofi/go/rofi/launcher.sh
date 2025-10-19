#!/bin/sh

SCRIPTPATH="$(
    cd -- "$(dirname "$0")" >/dev/null 2>&1 || exit 1
    pwd -P
)"

[ -f "$SCRIPTPATH/helper.sh" ] || {
    notify-send -i rofi -a pytfeeder "helper script not found"
    exit 1
}

# theme string
theme() {
    cat <<EOF
configuration {
  font: "NotoSansMono Nerd Font 16";
  kb-custom-1: "Ctrl+s";
  kb-custom-2: "Ctrl+x";
  kb-custom-3: "Ctrl+X";
  kb-move-front: "";
  kb-custom-4: "Ctrl+a";
  kb-remove-char-forward: "Delete";
  kb-custom-5: "Ctrl+d";
}
window {
  height: 90%;
}
inputbar {
  children: ["textbox-prompt-colon","entry","num-filtered-rows","textbox-num-sep","num-rows","case-indicator"];
}
textbox-prompt-colon {
  str: "";
  text-color: #f03;
  padding: 0 5px;
}
element.selected.urgent {
  background-color: #00000000;
}
EOF
}
N=1
[ -n "$1" ] && N="$1"
N="$N" SCRIPTPATH="$SCRIPTPATH" rofi -i -show "pytfeeder-rofi-launcher" \
    -modi "pytfeeder-rofi-launcher:$SCRIPTPATH/helper.sh" \
    -no-config -theme-str "$(theme)" \
    -eh "$N" -normal-window
