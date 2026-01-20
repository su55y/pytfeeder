#!/bin/sh

MODENAME=pytfeeder-rofi-go

SCRIPTPATH="$(
    cd -- "$(dirname "$0")" >/dev/null 2>&1 || exit 1
    pwd -P
)"

HELPER="$SCRIPTPATH/helper.sh"
if [ ! -f "$HELPER" ]; then
    printf '<b>%s</b>\n%s not found' "$MODENAME" "$HELPER" | rofi -markup -e -
    exit 1
fi

GO_HELPER="$SCRIPTPATH/go-ytfeeder-rofi"
if [ ! -f "$GO_HELPER" ]; then
    printf '<b>%s</b>\n%s not found' "$MODENAME" "$GO_HELPER" | rofi -markup -e -
    exit 1
fi

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
N="$N" SCRIPTPATH="$SCRIPTPATH" rofi -i -no-config \
    -show "$MODENAME" -modi "$MODENAME:$HELPER" \
    -eh "$N" -theme-str "$(theme)" \
    -normal-window
