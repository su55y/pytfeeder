import subprocess as sp

from pytfeeder.models import Entry


class Cmd:
    def __init__(self, play_cmd: list[str], notify_cmd: list[str]) -> None:
        self.__play_cmd = play_cmd
        self.__notify_cmd = notify_cmd

    def play_cmd(self, vid_id: str) -> list[str]:
        return [s.format(url=f"https://youtu.be/{vid_id}") for s in self.__play_cmd]

    def notify_cmd(self, msg: str) -> list[str]:
        return [s.format(msg=msg) for s in self.__notify_cmd]

    def download_video(
        self, entry: Entry, output: str, send_notification: bool = True
    ) -> None:
        p = sp.check_output(
            [
                "tsp",
                "-L",
                "pytfeeder",
                "yt-dlp",
                f"https://youtu.be/{entry.id}",
                "-o",
                output,
            ],
            shell=False,
        )

        if not send_notification:
            return

        _ = self.notify(f"⬇️Start downloading {entry.title!r}...")

        _ = sp.run(
            [
                "tsp",
                "-D",
                p.decode(),
                "notify-send",
                "-i",
                "youtube",
                "-a",
                "pytfeeder",
                f"✅Download done: {entry.title}",
            ],
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )

    def download_all(
        self,
        entries: list[Entry],
        output: str,
        send_notification: bool = False,
    ) -> None:
        if send_notification:
            _ = self.notify(f"⬇️Start downloading {len(entries)} entries...")
        for e in entries:
            self.download_video(e, output, send_notification)

    def play_video(self, entry: Entry, send_notification: bool = False) -> None:
        if send_notification:
            _ = self.notify(f"{entry.title} playing...")
        _ = sp.Popen(
            self.play_cmd(vid_id=entry.id),
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )

    def notify(self, msg: str) -> bool:
        if not msg:
            return True
        p = sp.run(self.notify_cmd(msg), stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        if p.returncode != 0:
            return False
        return True
