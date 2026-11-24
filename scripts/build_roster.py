import csv
import json
import re
from pathlib import Path


SOURCE = Path("build/catalog")
SHOWDOWN = "https://play.pokemonshowdown.com/sprites/"
DIGI_PATH = "digimon/sprites/"
FALLBACK = {"Normal": "normal", "Fire": "fire", "Water": "water", "Electric": "electric",
            "Grass": "grass", "Ice": "ice", "Fighting": "fighting", "Poison": "poison",
            "Ground": "ground", "Flying": "flying", "Psychic": "psychic", "Bug": "bug",
            "Rock": "rock", "Ghost": "ghost", "Dragon": "dragon", "Dark": "dark",
            "Steel": "steel", "Fairy": "fairy", "Stellar": "fairy"}
PREFERRED = {"pikachu": "thunder", "bulbasaur": "vinewhip", "charmander": "ember",
             "squirtle": "watergun", "eevee": "quickattack", "jigglypuff": "sing",
             "gengar": "shadowball", "charizard": "flamethrower", "mewtwo": "psystrike",
             "snorlax": "bodyslam", "psyduck": "confusion", "magikarp": "splash"}
DIGI_ALIASES = {
    "aruraumon": "alraumon", "beastmon": "bastemon", "biyomon": "piyomon",
    "blackagumon": "agumonblack", "blackgabumon": "gabumonblack",
    "blackgarurumon": "garurumonblack", "blackgreymon": "greymonblue",
    "blackmetalgarurumon": "metalgarurumonblack", "blackweregarurumon": "weregarurumonblack",
    "blackgatomon": "blacktailmon", "bukamon": "pukamon", "centarumon": "centalmon",
    "cherubimonevil": "cherubimonvice", "cherubimongood": "cherubimonvirtue",
    "demidevimon": "picodevimon", "diaboromon": "diablomon", "dolphmon": "rukamon",
    "darkrizamon": "darklizamon", "dorugreymon": "doruguremon", "flarerizamon": "flarelizamon",
    "frigimon": "yukidarumon", "gatomon": "tailmon", "gotsumon": "gottsumon",
    "herculeskabuterimon": "heraklekabuterimon", "hyogamon": "hyougamon",
    "iceleomon": "panjyamon", "kokatorimon": "cockatrimon", "lillymon": "lilimon",
    "machinedramon": "mugendramon", "magnaangemon": "holyangemon", "magnadramon": "holydramon",
    "marineangemon": "marinangemon", "megakabuterimon": "atlurkabuterimonred",
    "meicrackmonvm": "meicrackmonviciousmode", "metalgreymonvaccine": "metalgreymon",
    "meteormon": "insekimon", "motimon": "mochimon", "mudfrigimon": "tuchidarumon",
    "myotismon": "vamdemon", "ninjamon": "igamon", "ogremon": "orgemon",
    "omnimon": "omegamon", "omnimonzwart": "omegamonzwart", "ophanimon": "ofanimon",
    "penguinmon": "penmon", "phoenixmon": "hououmon", "piximon": "piccolomon",
    "piddomon": "pidmon", "redvegiemon": "redvegimon", "rockmon": "golemon", "salamon": "plotmon",
    "shamanmon": "shamamon", "tyrannomon": "tyranomon",
    "shogungekomon": "tonosamagekomon", "snowagumon": "yukiagumon",
    "tsukaimon": "tukaimon", "tsunomon": "tunomon",
    "vegiemon": "vegimon", "venommyotismon": "venomvamdemon",
    "vermilimon": "vermillimon", "weedmon": "zassoumon",
}
DIGI_NAMES = {"agumon": "아구몬", "gabumon": "파피몬", "patamon": "파닥몬",
              "gatomon": "가트몬", "gomamon": "쉬라몬", "tentomon": "텐타몬",
              "palmon": "팔몬", "biyomon": "피요몬", "greymon": "그레이몬",
              "mudfrigimon": "머드프리지몬", "garurumon": "가루몬", "wargreymon": "워그레이몬", "omnimon": "오메가몬"}
DIGI_PREFERRED = {"agumon": ("작은 불꽃", "fire"), "gabumon": ("푸른 불꽃", "fire"),
                  "patamon": ("공기포", "flying"), "gatomon": ("고양이 펀치", "fighting"),
                  "greymon": ("메가 플레임", "fire"), "garurumon": ("폭스 파이어", "fire")}


def ident(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def read_json(name):
    return json.loads((SOURCE / name).read_bytes())


def sprite_files(folder):
    html = (SOURCE / folder).read_text(encoding="utf-8")
    return re.findall(r'href="\./([a-zA-Z0-9_%-]+\.(?:gif|png))"', html)


def translations(filename, key):
    with (SOURCE / filename).open(encoding="utf-8", newline="") as stream:
        return {int(row[key]): row["name"] for row in csv.DictReader(stream)
                if row["local_language_id"] == "3"}


def pokemon_entries():
    dex = read_json("pokedex")
    learns = read_json("learnsets")
    moves = read_json("moves")
    names = translations("names", "pokemon_species_id")
    move_names = translations("movename", "move_id")
    sprites = {ident(Path(file).stem): ("ani/" + file) for file in sprite_files("ani")}
    for folder in ("dex", "home"):
        sprites.update({key: folder + "/" + file for file in sprite_files(folder)
                        if (key := ident(Path(file).stem)) not in sprites})
    for key, mon in dex.items():
        if mon.get("num", 0) <= 0 or key not in sprites:
            continue
        candidates = {}
        current = mon
        seen = set()
        while current:
            current_key = ident(current["name"])
            if current_key in seen:
                break
            seen.add(current_key)
            candidates.update(learns.get(current_key, {}).get("learnset", {}))
            current = dex.get(ident(current.get("changesFrom") or current.get("baseSpecies")
                                    or current.get("prevo") or ""))
            if current and ident(current["name"]) in seen:
                current = dex.get(ident(current.get("prevo", "")))
        options = [moves[move] for move in candidates if move in moves and moves[move].get("num", 0) > 0]
        selected = moves.get(PREFERRED.get(key)) if PREFERRED.get(key) in candidates else None
        if selected is None and options:
            primary = mon["types"][0]
            selected = max(options, key=lambda move: (
                move["type"] == primary and move["basePower"] > 0,
                move["type"] in mon["types"] and move["basePower"] > 0,
                move["basePower"] > 0, min(move["basePower"], 95)))
        if selected:
            skill = move_names.get(selected["num"], selected["name"])
            effect = FALLBACK.get(selected["type"], "normal")
        else:
            skill, effect = "타입 에너지", FALLBACK.get(mon["types"][0], "normal")
        name = names.get(mon["num"], mon["name"])
        if mon.get("forme"):
            name += " · " + mon["forme"]
        yield ["pokemon:" + key, name, mon["name"], sprites[key], skill, effect]


def digi_inputs():
    listings = {ident(item["name"].replace("-Antibody", "").replace(" Antibody", "")): item
                for item in read_json("digiapi")["content"]}
    sprites = {Path(file).stem: DIGI_PATH + "digimon/" + file for file in sprite_files("digimon")}
    sprites.update({Path(file).stem: DIGI_PATH + "digimonani/" + file
                    for file in sprite_files("digimonani")})
    for key, sprite in sorted(sprites.items()):
        base = key[:-1] if key.endswith("x") else key
        alias = DIGI_ALIASES.get(base, base)
        lookup = alias + ("x" if base != key else "")
        item = listings.get(key) or listings.get(lookup)
        if not item and base != key:
            item = listings.get(base) or listings.get(alias)
        yield key, sprite, item


def digi_type(text):
    for effect, terms in {
        "fire": ("fire", "flame", "burn", "heat"), "water": ("water", "aqua", "bubble"),
        "electric": ("electric", "thunder", "lightning"), "ice": ("ice", "freeze", "snow"),
        "grass": ("leaf", "plant", "vine", "flower", "poison ivy"),
        "dark": ("dark", "evil", "shadow", "hell", "night"),
        "flying": ("wing", "air", "wind", "feather"), "fighting": ("punch", "kick", "claw", "fist"),
        "steel": ("missile", "metal", "cannon", "laser"), "fairy": ("holy", "light", "angel"),
        "rock": ("stone", "rock"),
    }.items():
        if any(term in text.lower() for term in terms):
            return effect
    return "normal"


def digimon_entries():
    for key, sprite, item in digi_inputs():
        detail = SOURCE / "digi-details" / str(item["id"]) if item else None
        data = json.loads(detail.read_bytes()) if detail and detail.exists() else {}
        skills = data.get("skills", [])
        move = next((skill for skill in skills if skill.get("skill") and skill["skill"] != "-"), None)
        if key in DIGI_PREFERRED:
            skill, effect = DIGI_PREFERRED[key]
        elif move:
            skill = move["skill"]
            effect = digi_type(skill + " " + (move.get("description") or ""))
        else:
            skill, effect = "데이터 파동", "steel"
        english = item["name"] if item else key.capitalize()
        if key.endswith("x") and not ident(english.replace("-Antibody", "")).endswith("x"):
            english += " (X)"
        yield ["digimon:" + key, DIGI_NAMES.get(key, english), english, sprite, skill, effect]


if __name__ == "__main__":
    rows = [*pokemon_entries(), *digimon_entries()]
    Path("assets/roster.json").write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
                                         encoding="utf-8")
    print(f"{len(rows)} entries, {sum(row[4] in ('타입 에너지', '데이터 파동') for row in rows)} fallback")


