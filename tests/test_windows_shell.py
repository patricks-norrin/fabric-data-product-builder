import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class WindowsShellTests(unittest.TestCase):
    def test_fab_common_falls_back_to_python_when_python3_is_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            bin_dir = pathlib.Path(temp)
            os.symlink(sys.executable, bin_dir / "python")
            for tool in ("bash", "dirname", "tr"):
                os.symlink(shutil.which(tool), bin_dir / tool)

            result = subprocess.run(
                ["bash", "-c", f'source "{ROOT}/scripts/fab_common.sh"; python3 -c "print(1 + 1)"; echo "$MSYS_NO_PATHCONV"'],
                env={"PATH": str(bin_dir)}, capture_output=True, text=True, timeout=30,
            )

            self.assertEqual(result.stdout.split(), ["2", "1"], result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
