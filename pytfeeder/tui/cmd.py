import subprocess as sp

from pytfeeder.models import Entry


class Cmd:
    def __init__(
        self,
        play_cmd: str,
        notify_cmd: str,
        download_cmd: str,
        download_output: str,
    ) -> None:
        self.play_cmd = play_cmd
        self.notify_cmd = notify_cmd
        self.download_cmd = download_cmd
        self.download_output = download_output
        self.send_notification = True

    def yt_url(self, vid_id: str) -> str:
        return f"https://youtu.be/{vid_id}"

    def _exec_cmd(self, cmd: str) -> None:
        _ = sp.Popen(cmd, shell=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL)

    def download_video(self, entry: Entry) -> None:
        _ = self.notify(f"⬇️Start downloading {entry.title!r}...")
        cmd = self.download_cmd.format(
            url=self.yt_url(entry.id),
            title=entry.title.replace("'", ""),
            output=self.download_output,
        )
        self._exec_cmd(cmd)

    def download_all(self, entries: list[Entry]) -> None:
        _ = self.notify(f"⬇️Start downloading {len(entries)} entries...")
        for e in entries:
            self.download_video(e)

    def play_video(self, entry: Entry) -> None:
        _ = self.notify(f"{entry.title} playing...")
        cmd = self.play_cmd.format(url=self.yt_url(entry.id))
        self._exec_cmd(cmd)

    def notify(self, msg: str) -> None:
        if not msg or not self.send_notification:
            return
        cmd = self.notify_cmd.format(msg=msg.replace("'", ""))
        self._exec_cmd(cmd)
