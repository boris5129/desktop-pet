# 이미지와 소리 출처

- 원본 GIF는 Pokémon Showdown 스프라이트 디렉터리의 피카츄 파일입니다. 다운로드 응답은 HTTP 200이었고 로컬 헤더는 GIF89a입니다. Qt에서 60 × 60픽셀, 33프레임과 투명 픽셀을 확인했습니다. [스프라이트 목록](https://play.pokemonshowdown.com/sprites/) · [원본 파일](https://play.pokemonshowdown.com/sprites/ani/pikachu.gif)
- 트레이·실행파일 아이콘은 같은 GIF의 첫 프레임을 사용합니다. 걷기·수면 전용 그림 대신 기본 GIF와 화면 이동, 점프, Zzz 오버레이로 표현합니다. 효과음은 두 주파수의 사인파로 만든 WAV입니다.
- 피카츄와 Pokémon 관련 권리는 각 권리자에게 있습니다. Showdown에서의 공개 제공만으로 해당 스프라이트의 독립 재배포나 상업적 사용에 대한 허가를 확인할 수 없습니다. 이 결과물의 용도는 개인 학습 및 비상업적 프로토타입입니다.

## 친구 선택 목록

- 포켓몬 선택 목록은 Showdown의 ani, dex, home 디렉터리와 도감 데이터를 대조했습니다. 동일 캐릭터의 여러 이미지가 있으면 GIF를 우선합니다. Showdown의 기술·습득 데이터에서 실제로 배울 수 있는 기술 하나를 골랐고, PokéAPI의 한국어 이름을 이용했습니다. [스프라이트 디렉터리](https://play.pokemonshowdown.com/sprites/) · [도감 데이터](https://play.pokemonshowdown.com/data/) · [PokéAPI 이름 데이터](https://github.com/PokeAPI/pokeapi/tree/master/data/v2/csv)
- 디지몬은 Showdown 디렉터리의 233개 스프라이트를 사용했고, DAPI의 종별 기술 데이터와 대조했습니다. 일부 디지몬과 폼의 이름 및 기술명은 영문으로 표시됩니다. [Showdown 디지몬 스프라이트](https://play.pokemonshowdown.com/sprites/digimon/sprites/digimonani/) · [DAPI](https://digi-api.com/)
- 기술 연출은 타입별 색상과 움직임으로 그립니다. 피카츄가 사용하는 낙뢰 연출도 포함됩니다. 선택한 파일은 첫 사용 시 HTTPS로 받아 로컬에 캐시합니다. 기본 포함 친구는 피카츄, 이상해씨, 파이리, 꼬부기, 이브이, 아구몬, 파피몬, 파닥몬, 가트몬입니다.

## 배틀타워 상대 이미지와 능력치

포켓몬의 진화 단계와 종별 능력치는 Showdown 도감 데이터를 참고했습니다. 디지몬의 진화 단계는 DAPI를 참고했으며, 배틀 능력치는 앱의 단계별 밸런스에 맞춰 계산합니다. 타워 상대 이미지는 Showdown에 있는 각 스프라이트의 첫 프레임을 사용합니다. [Showdown 도감 데이터](https://play.pokemonshowdown.com/data/) · [DAPI](https://digi-api.com/)

## 아구몬 스프라이트 시범 적용

- 참고 Reddit 글의 Google Drive에서 공개 `Animations`와 `Frames` 폴더 및 아구몬 하위 목록을 확인했습니다. 아구몬 항목에는 PNG 36장과 별도의 Spine용 .atlas·.json·.png 묶음이 나열됩니다. 게시자는 이를 게임에서 추출했다고 설명합니다. 두 공유 목록에서 별도 라이선스 문서나 재배포 허가를 확인하지 못했습니다. DIGIMON UP의 추출 파일은 시범판에 포함되어 있지 않습니다. [참고 게시물](https://www.reddit.com/r/digimon/comments/1xloq6t/i_actually_extracted_every_digimon_up_sprite_with/) · [공개 폴더](https://drive.google.com/drive/folders/1FVFVnQtGcL0tNuf_rwcP41lCnYMhkNfr) · [공식 사이트](https://dgup.bn-ent.net/en/)
- 시범판은 프로젝트에 포함돼 있던 Pokémon Showdown의 아구몬 GIF를 사용합니다. 파일의 팔레트와 투명도는 그대로 두고 상태에 따라 기존 프레임 순서와 속도를 선택합니다. 식사는 프레임과 몸짓, 수면은 눈을 감은 프레임과 호흡 효과를 조합합니다. [아구몬 GIF 원본](https://play.pokemonshowdown.com/sprites/digimon/sprites/digimonani/agumon.gif)

