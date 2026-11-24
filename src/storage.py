import json
import os
from dataclasses import asdict, fields
from datetime import datetime

from src.model import Pet, Settings, now


def restore(cls, data):
    if not isinstance(data, dict):
        raise ValueError("invalid object")
    defaults = cls()
    values = {}
    for field in fields(cls):
        if field.name in data:
            value = data[field.name]
            if type(value) is not type(getattr(defaults, field.name)):
                raise ValueError(field.name)
            values[field.name] = value
    return cls(**values)


class Store:
    def __init__(self, directory):
        self.directory = directory
        self.path = directory / "pet.json"
        self.backup = directory / "pet.backup.json"
        self.directory.mkdir(parents=True, exist_ok=True)

    def load(self):
        for path in (self.path, self.backup):
            try:
                pet, settings = self.read(path)
                return pet, settings
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return Pet(), Settings()

    def read(self, path):
        data = json.loads(path.read_text(encoding="utf-8"))
        pet = restore(Pet, data["pet"])
        settings = restore(Settings, data["settings"])
        for value in (pet.created, pet.last_seen, pet.last_meal or pet.created):
            if datetime.fromisoformat(value).tzinfo is None:
                raise ValueError("invalid timestamp")
        if not all(type(v) in (float, int) and 0 <= v < 900 for v in pet.elapsed.values()):
            raise ValueError("invalid elapsed time")
        if not (1 <= pet.level and 0 <= pet.xp < pet.target and 64 <= settings.size <= 240
                and 30 <= settings.speed <= 240):
            raise ValueError("invalid range")
        pet.change()
        if pet.state != "수면":
            pet.state = "대기"
        return pet, settings

    @staticmethod
    def replace(path, content):
        temporary = path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)

    def save(self, pet, settings):
        try:
            self.read(self.path)
            old = self.path.read_text(encoding="utf-8")
        except (OSError, ValueError, KeyError, TypeError):
            old = None
        pet.last_seen = now()
        current = json.dumps({"pet": asdict(pet), "settings": asdict(settings)},
                             ensure_ascii=False, indent=2)
        if old is not None:
            self.replace(self.backup, old)
        self.replace(self.path, current)
        if not self.backup.exists():
            self.replace(self.backup, current)
