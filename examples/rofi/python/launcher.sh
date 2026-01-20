#!/bin/sh

MODENAME=pytfeeder-rofi

SCRIPTPATH="$(
    cd -- "$(dirname "$0")" >/dev/null 2>&1 || exit 1
    pwd -P
)"

HELPER="$SCRIPTPATH/helper.sh"
if [ ! -f "$HELPER" ]; then
    printf '<b>%s</b>\n%s not found' "$MODENAME" "$HELPER" | rofi -markup -e -
    exit 1
fi

PY_HELPER="$SCRIPTPATH/helper.py"
if [ ! -f "$PY_HELPER" ]; then
    printf '<b>%s</b>\n%s not found' "$MODENAME" "$PY_HELPER" | rofi -markup -e -
    exit 1
fi

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

PY_HELPER="$PY_HELPER" rofi -i -no-config \
    -show "$MODENAME" -modi "$MODENAME:$HELPER" \
    -eh 2 -theme-str "$(theme)" \
    -normal-window
