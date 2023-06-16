#!/bin/sh

SCRIPTPATH="$(cd -- "$(dirname "$0")" >/dev/null 2>&1 || exit 1 ; pwd -P)"

[ -f "$SCRIPTPATH/helper.sh" ] || {
    notify-send -i "rofi" -a "youtube feed" "helper script not found"
    exit 1
}


# theme string
theme() { cat <<EOF
configuration {
  font: "NotoSans Nerd Font 16";
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
element selected urgent {
  background-color: #f00;
  text-color: #111;
}
element normal urgent {
  background-color: #e00;
  text-color: #000;
}
element alternate urgent {
  background-color: #e00;
  text-color: #000;
}
EOF
}

rofi -i -show "yt_feed_rofi"\
    -modi "yt_feed_rofi:$SCRIPTPATH/helper.sh"\
    -no-config\
    -no-custom\
    -kb-custom-1 "Ctrl+c"\
    -kb-move-front "Ctrl+i"\
    -kb-custom-2 "Ctrl+a"\
    -kb-row-select "Ctrl+9"\
    -kb-custom-3 "Ctrl+space"\
    -theme-str "$(theme)"\
    -normal-window
