"""Exercise the frozen app on a Windows desktop using an isolated data directory."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.FindWindowExW.argtypes = (wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR)
user32.FindWindowExW.restype = wintypes.HWND
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = (
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
TITLE = "피카츄 데스크톱 펫"
STARTER_NAMES = {"pokemon:charmander": "파이리", "pokemon:squirtle": "꼬부기",
                 "pokemon:bulbasaur": "이상해씨", "digimon:agumon": "아구몬",
                 "digimon:gabumon": "파피몬"}


def find_test_window(executable, title=TITLE):
    hwnd = None
    while hwnd := user32.FindWindowExW(None, hwnd, None, title):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(0x1000, False, pid.value)
        if not handle:
            continue
        try:
            image = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(image))
            if kernel32.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
                if Path(image.value) == executable:
                    return hwnd
        finally:
            kernel32.CloseHandle(handle)
    return None


def wait_for_window(process, data, executable, title=TITLE):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"앱 종료 코드 {process.returncode}: {(executable.parent / 'stderr.log').read_bytes()[-3500:]!r}")
        hwnd = find_test_window(executable, title)
        if hwnd and data.exists():
            return hwnd
        time.sleep(0.2)
    raise RuntimeError("앱 창 또는 저장 파일을 찾지 못했습니다.")


def sample(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    command = f"$p=Get-Process -Id {pid.value}; [string]$p.CPU + ' ' + [string]$p.WorkingSet64"
    result = subprocess.check_output(["powershell", "-NoProfile", "-Command", command], text=True)
    cpu, memory = result.split()
    return float(cpu), int(memory) / (1024 * 1024)


def close(hwnd, process):
    assert user32.PostMessageW(hwnd, 0x0010, 0, 0)
    assert process.wait(timeout=15) == 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument("--exe", type=Path, default=Path("dist/PikachuDesktopPet.exe"))
    parser.add_argument("--friends", action="store_true")
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--fresh-economy", action="store_true")
    args = parser.parse_args()
    if args.fresh_economy and (args.friends or args.online):
        parser.error("--fresh-economy and a pre-owned roster cannot be combined")
    executable = args.exe.resolve()
    output = Path("build").resolve()
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output, prefix="배포검증-") as directory:
        root = Path(directory)
        bundled = root / executable.name
        shutil.copyfile(executable, bundled)
        data = root / "PikachuDesktopPet" / "pet.json"
        profile = data.parent
        economy_path = profile / "economy.json"
        env = {**os.environ, "LOCALAPPDATA": str(root), "TEMP": str(root),
               "TMP": str(root), "PATH": str(Path(os.environ["SystemRoot"]) / "System32")}
        processes = []
        if args.friends or args.online:
            friends = [("pokemon:charmander", "파이리"), ("digimon:agumon", "아구몬")]
            if args.online:
                friends.append(("pokemon:pecharunt", "복숭악동"))
            data.parent.mkdir()
            keys = ["pokemon:pikachu", *(key for key, _ in friends)]
            data.with_name("economy.json").write_text(json.dumps({
                "starter": "pokemon:charmander", "gold": 0, "cleared": 0,
                "owned": {key: 0 for key in keys},
            }), encoding="utf-8")
            data.with_name("roster.json").write_text(
                json.dumps(keys), encoding="utf-8")
        else:
            friends = []

        def launch():
            with (root / "stderr.log").open("ab") as error_log:
                process = subprocess.Popen([str(bundled)], cwd=root, env=env, stderr=error_log)
            processes.append(process)
            return process

        def verify_friends(process, shared_size=None):
            for key, name in friends:
                category, species = key.split(":")
                saved = data.parent / "pets" / category / species / "pet.json"
                wait_for_window(process, saved, bundled, f"{name} 데스크톱 펫")
                payload = json.loads(saved.read_text(encoding="utf-8"))
                assert payload["pet"]["name"] == name
                if shared_size is not None:
                    assert payload["settings"]["size"] == shared_size
            if args.online:
                assert (data.parent / "sprites" / "pokemon" / "pecharunt.png").is_file()

        try:
            first = launch()
            title = TITLE
            name = "피카츄"
            if args.fresh_economy:
                deadline = time.monotonic() + 30
                while not economy_path.is_file() and first.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.1)
                economy = json.loads(economy_path.read_bytes())
                starter = economy["starter"]
                assert economy["owned"] == {starter: 0} and economy["gold"] == 0
                category, species = starter.split(":")
                name = STARTER_NAMES[starter]
                title = f"{name} 데스크톱 펫"
                data = profile / "pets" / category / species / "pet.json"
            hwnd = wait_for_window(first, data, bundled, title)
            assert json.loads(data.read_text(encoding="utf-8"))["pet"]["name"] == name
            verify_friends(first)
            duplicate = launch()
            assert duplicate.wait(timeout=30) == 0 and first.poll() is None
            baseline = sample(hwnd)
            begin = time.monotonic()
            samples = [baseline]
            while time.monotonic() - begin < args.seconds:
                time.sleep(min(10, max(0, args.seconds - (time.monotonic() - begin))))
                assert first.poll() is None
                samples.append(sample(hwnd))
            elapsed = time.monotonic() - begin
            load = (samples[-1][0] - baseline[0]) / elapsed * 100
            print(f"{elapsed:.1f}s, one-core CPU {load:.2f}%, "
                  f"working set {baseline[1]:.1f} -> {samples[-1][1]:.1f} MiB, "
                  f"peak {max(value[1] for value in samples):.1f} MiB")
            close(hwnd, first)
            assert not (profile / "instance.lock").exists()
            saved = json.loads(data.read_text(encoding="utf-8"))
            saved["pet"]["xp"] = 47
            saved["settings"]["size"] = 136
            data.write_text(json.dumps(saved), encoding="utf-8")
            second = launch()
            hwnd = wait_for_window(second, data, bundled, title)
            if args.fresh_economy:
                assert json.loads(economy_path.read_bytes()) == economy
            verify_friends(second, shared_size=136)
            close(hwnd, second)
            saved = json.loads(data.read_text(encoding="utf-8"))
            assert (saved["pet"]["xp"], saved["settings"]["size"]) == (47, 136)
            print("Frozen app launch, duplicate guard, graceful exit and restore passed.")
            if friends:
                print(f"{len(friends) + 1} simultaneous pet windows and separate save files passed.")
            if args.fresh_economy:
                print("Exactly one random starter granted and restored on relaunch.")
        finally:
            remaining = find_test_window(bundled, title)
            if remaining:
                user32.PostMessageW(remaining, 0x0010, 0, 0)
            for process in processes:
                if process.poll() is None:
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


if __name__ == "__main__":
    main()



