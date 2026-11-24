from importlib.util import find_spec
from pathlib import Path

qt = Path(find_spec("PySide6").origin).parent
crt = {
    name: str(qt / name)
    for name in ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll",
                 "msvcp140_1.dll", "msvcp140_2.dll")
}
analysis = Analysis(["main.py"], datas=[("assets", "assets")])
# The frozen Python DLL loads the root CRT before Qt imports. Use Qt's
# newer compatible CRT so both consumers share a matching runtime.
# Do not package an unrelated ICU DLL discovered on the build host PATH.
analysis.binaries = [
    entry for entry in analysis.binaries
    if entry[0].lower() not in crt
    and not (Path(entry[0]).name.lower().startswith("icu")
             and not Path(entry[1]).is_relative_to(qt))
]
analysis.binaries.extend((name, path, "BINARY") for name, path in crt.items())
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz, analysis.scripts, analysis.binaries, analysis.datas,
    name="PikachuDesktopPet", console=False, icon="assets/icons/pikachu.ico",
)

