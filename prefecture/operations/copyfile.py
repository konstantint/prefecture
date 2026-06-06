"""CopyFile task for Prefecture."""

import pathlib
import shutil

import prefect


class CopyFile:
    """Copies a file from one location to another."""

    def __init__(
        self,
        *,
        config_dir: pathlib.Path,
        run_dir: pathlib.Path,
        from_path: str,
        to_path: str,
    ):
        """Initializes the CopyFile task."""
        self.config_dir = config_dir
        self.run_dir = run_dir
        self.from_path = from_path
        self.to_path = to_path

    @prefect.task(name="CopyFile")
    def __call__(self) -> None:
        """Copies the file."""
        src = pathlib.Path(self.from_path)
        if not src.is_absolute():
            src = self.run_dir / src

        dst = pathlib.Path(self.to_path)
        if not dst.is_absolute():
            dst = self.run_dir / dst

        # Ensure destination directory exists
        dst.parent.mkdir(parents=True, exist_ok=True)

        print(f"Copying {src} to {dst}")
        shutil.copy(src, dst)

    @property
    def dependencies(self) -> set[str]:
        path = pathlib.Path(self.from_path)
        if not path.is_absolute():
            path = self.run_dir / path
        return {str(path.resolve())}

    @property
    def outputs(self) -> set[str]:
        path = pathlib.Path(self.to_path)
        if not path.is_absolute():
            path = self.run_dir / path
        return {str(path.resolve())}

