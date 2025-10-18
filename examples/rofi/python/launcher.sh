#!/bin/sh

SCRIPTPATH="$(
    cd -- "$(dirname "$0")" >/dev/null 2>&1 || exit 1
    pwd -P
)"

[ -f "$SCRIPTPATH/helper.sh" ] || {
    notify-send -i rofi -a pytfeeder-rofi 'helper script not found'
    exit 1
}

[ -f "$SCRIPTPATH/helper.py" ] || {
    notify-send -i rofi -a pytfeeder-rofi 'py helper script not found'
    exit 1
}

theme() {
    cat <<EOF
configuration {
  font: "NotoSans Nerd Font 16";
  kb-custom-1: "Ctrl+s";
  kb-custom-2: "Ctrl+x";
  kb-custom-3: "Ctrl+X";
  kb-move-front: "";
  kb-custom-4: "Ctrl+a";
  kb-remove-char-forward: "Delete";
  kb-custom-5: "Ctrl+d";
  kb-mode-next: "Shift+Right";
  kb-custom-6: "Ctrl+Tab";
}
window {
  height: 90%;
}
inputbar {
  children: ["textbox-prompt-colon","entry","num-filtered-rows","textbox-num-sep","num-rows","case-indicator"];
}
textbox-prompt-colon {
  str: "";
  text-color: #f00;
  padding: 0 5px;
}
element.selected.urgent {
  background-color: #00000000;
}
EOF
}

HELPER="$SCRIPTPATH/helper.py" rofi -i -show pytfeeder-rofi \
    -modi "pytfeeder-rofi:$SCRIPTPATH/helper.sh" \
    -no-config -theme-str "$(theme)" \
    -normal-window -eh 2
