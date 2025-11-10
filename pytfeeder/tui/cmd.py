import subprocess as sp

from pytfeeder.models import Entry


class Cmd:
    def __init__(self, play_cmd: list[str], notify_cmd: list[str]) -> None:
        self.__play_cmd = play_cmd
        self.__notify_cmd = notify_cmd
        self.send_notification = True

    def play_cmd(self, vid_id: str) -> list[str]:
        return [s.format(url=f"https://youtu.be/{vid_id}") for s in self.__play_cmd]

    def notify_cmd(self, msg: str) -> list[str]:
        return [s.format(msg=msg) for s in self.__notify_cmd]

    def download_video(self, entry: Entry, output: str) -> None:
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

        _ = self.notify(f"⬇️Start downloading {entry.title!r}...")

        if self.send_notification:
            _ = sp.run(
                [
                    "tsp",
                    "-D",
                    p.decode(),
                    *self.notify_cmd(f"✅Download done: {entry.title}"),
                ],
                stdout=sp.DEVNULL,
                stderr=sp.DEVNULL,
            )

    def download_all(self, entries: list[Entry], output: str) -> None:
        _ = self.notify(f"⬇️Start downloading {len(entries)} entries...")
        for e in entries:
            self.download_video(e, output)

    def play_video(self, entry: Entry) -> None:
        _ = self.notify(f"{entry.title} playing...")
        _ = sp.Popen(
            self.play_cmd(vid_id=entry.id),
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )

    def notify(self, msg: str) -> bool:
        if not msg or not self.send_notification:
            return True
        p = sp.run(self.notify_cmd(msg), stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        if p.returncode != 0:
            return False
        return True
