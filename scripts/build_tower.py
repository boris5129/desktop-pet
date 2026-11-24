import json
from pathlib import Path
from zlib import crc32

from build_roster import SOURCE, digi_inputs, ident, read_json


def evolution_stage(key, dex):
    stage = 0
    seen = set()
    while key in dex and key not in seen:
        seen.add(key)
        entry = dex[key]
        parent = entry.get("prevo")
        if parent:
            stage += 1
        else:
            parent = entry.get("changesFrom") or entry.get("baseSpecies")
            if parent and (entry.get("forme", "").startswith("Mega") or entry.get("forme") == "Gmax"):
                stage += 1
        if not parent:
            break
        key = ident(parent)
    return stage


def build():
    entries = json.loads(Path("assets/roster.json").read_bytes())
    dex = read_json("pokedex")
    digimon = {key: item for key, _, item in digi_inputs()}
    data = {}
    tiers = [[], [], [], []]
    for key, _, _, _, _, _ in entries:
        category, species = key.split(":")
        if category == "pokemon":
            entry = dex[species]
            base = entry["baseStats"]
            hp = base["hp"]
            attack = (base["atk"] + base["spa"]) // 2
            defense = (base["def"] + base["spd"]) // 2
            stage = evolution_stage(species, dex)
            tier = min(3, stage)
            if entry.get("forme"):
                include = tier == 3 and entry["forme"].startswith("Mega")
            else:
                include = tier > 0 or bool(entry.get("evos")) or sum(base.values()) <= 430
        else:
            item = digimon[species]
            entry = json.loads((SOURCE / "digi-details" / str(item["id"])).read_bytes())
            levels = {"Baby I": 0, "Baby II": 0, "Child": 0, "Adult": 1, "Perfect": 2, "Ultimate": 3}
            stage = max((levels.get(level["level"], 0) for level in entry.get("levels", [])), default=0)
            seed = crc32(species.encode("ascii"))
            hp = 28 + stage * 20 + seed % 21
            attack = 27 + stage * 20 + (seed >> 8) % 22
            defense = 25 + stage * 20 + (seed >> 16) % 23
            tier, include = stage, not species.endswith("x")
        data[key] = [stage, hp, attack, defense]
        if include:
            tiers[tier].append((hp + attack + defense + stage * 36, key))

    floors = []
    for tier in tiers:
        tier.sort()
        floors.extend(tier[round(index * (len(tier) - 1) / 24)][1] for index in range(25))
    Path("assets/battle_roster.json").write_text(
        json.dumps({"profiles": data, "floors": floors}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    Path("build/tower-sprites.json").write_text(
        json.dumps({str(i): entry[3] for i, key in enumerate(floors, 1)
                    for entry in entries if entry[0] == key}), encoding="utf-8")
    print(f"{len(data)} profiles, {len(floors)} tower floors:", [len(tier) for tier in tiers])


if __name__ == "__main__":
    build()
