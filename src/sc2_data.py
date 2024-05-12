"""
Parses all relevant game data and strings, and stores them in appropriate dataclasses.
"""

import xml.etree.ElementTree
import typing
import logging
import dataclasses
import csv
import re
import numexpr  # type: ignore

import xml_helper
import utils
import sc2_globals
import dref

logger = logging.getLogger(__name__)
Element = xml.etree.ElementTree.Element


@dataclasses.dataclass
class UnitCost:
    minerals: float
    vespene: float
    supply: float


@dataclasses.dataclass
class UnitBonuses:
    dps_bonus_add: float
    dps_bonus_mult: float
    life_bonus_add: float
    life_bonus_mult: float
    wpn_bonus_add: float
    wpn_bonus_mult: float
    wpn_period_mult: float
    sort_with_dps_bonus: bool
    sort_with_life_bonus: bool


@dataclasses.dataclass
class Damage:
    id: str
    min: float
    max: float
    kind: str
    dmg_type: str
    effect_type: str  # Type field in effect

    def get_avg_dmg(self) -> float:
        return (self.min + self.max) / 2


@dataclasses.dataclass
class Weapon:
    id: str
    name: str
    damage: Damage
    period: float
    targets: int
    range: float
    melee: bool


@dataclasses.dataclass
class Unit:
    id: str
    name: str
    wpn: Weapon
    hp: float
    shields: float
    energy: float
    armor: str
    cost: UnitCost
    move_speed: float
    abilities: list[str]  # abil names (used as keys in ability dict data)
    bonuses: UnitBonuses

    def calculate_dps(self, check_if_excluded: bool = False) -> float:
        d = self.dps_bonus_formula_dict_fields(check_if_excluded)
        form = sc2_globals.DPS_FORMULA.format(**d)
        return float(numexpr.evaluate(form))

    def dps_bonus_formula_dict_fields(self, check_if_excluded: bool = False) -> dict[str, typing.Any]:
        d = {}
        check = self.bonuses.sort_with_dps_bonus if check_if_excluded else True
        d['dps_bonus_mult'] = self.bonuses.dps_bonus_mult if check else 1.0
        d['dps_bonus_add'] = self.bonuses.dps_bonus_add if check else 0.0
        d['wpn_bonus_add'] = self.bonuses.wpn_bonus_add if check else 0.0
        d['wpn_bonus_mult'] = self.bonuses.wpn_bonus_mult if check else 1.0
        d['wpn_period_mult'] = self.bonuses.wpn_period_mult if check else 1.0
        d['targets'] = self.wpn.targets
        d['min'] = self.wpn.damage.min
        d['max'] = self.wpn.damage.max
        d['period'] = self.wpn.period
        return d

    def calculate_life(self, check_if_excluded: bool = False) -> float:
        d = self.life_bonus_formula_dict_fields(check_if_excluded)
        form = sc2_globals.LIFE_FORMULA.format(**d)
        return float(numexpr.evaluate(form))

    def life_bonus_formula_dict_fields(self, check_if_excluded: bool = False) -> dict[str, typing.Any]:
        d = {}
        check = self.bonuses.sort_with_life_bonus if check_if_excluded else True
        d['life_bonus_mult'] = self.bonuses.life_bonus_mult if check else 1.0
        d['life_bonus_add'] = self.bonuses.life_bonus_add if check else 0.0
        d['hp'] = self.hp
        d['shields'] = self.shields
        return d


@dataclasses.dataclass
class Tower(Unit):
    tier: str
    builder: str
    upgrades: list[str]
    predecessors: list[str]


@dataclasses.dataclass
class Wave(Unit):
    index: int
    bounty: float
    count: int

    def get_wave_bonus(self) -> int:
        return 12 + int(self.index * 5 / 3)


@dataclasses.dataclass
class Send(Unit):
    bounty: float
    income: int


@dataclasses.dataclass
class Ability():
    name: str
    desc: str


@dataclasses.dataclass
class GameData:
    towers: dict[str, Tower]
    sends: dict[str, Send]
    waves: dict[str, Wave]
    abils: dict[str, Ability]


def get_game_string(key: str, default: typing.Optional[str]) -> typing.Optional[str]:
    val = sc2_globals.gGameStrings.get(key)
    if val is None:
        logger.warning('Missing game text: %r', key)
        val = default
    return val


@typing.overload
def get_game_tooltip(entry_id: str, catalog: str = 'Button', default: str = '') -> str:
    ...


@typing.overload
def get_game_tooltip(entry_id: str, catalog: str = 'Button', default: None = None) -> typing.Optional[str]:
    ...


def get_game_tooltip(entry_id: str, catalog: str = 'Button', default: typing.Optional[str] = None) -> typing.Optional[str]:
    key = f'{catalog}/Tooltip/{entry_id}'
    return get_game_string(key, default)


@typing.overload
def get_game_name(catalog: str, entry_id: str, default: str) -> str:
    ...


@typing.overload
def get_game_name(catalog: str, entry_id: str, default: None = None) -> typing.Optional[str]:
    ...


def get_game_name(catalog: str, entry_id: str, default: typing.Optional[str] = None) -> typing.Optional[str]:
    key = f'{catalog}/Name/{entry_id}'
    return get_game_string(key, default)


def parse_unit_bonuses(name: str, bonuses: dict[str, dict[str, str]]) -> UnitBonuses:
    unit_bonuses = bonuses.get(name)
    if unit_bonuses is None:
        logger.warning("bonuses not found for %s", name)
        return UnitBonuses(0, 1, 0, 1, 0, 1, 1, True, True)
    ret: dict[str, typing.Any] = {}
    ret['dps_bonus_add'] = float(unit_bonuses['dps_bonus_add'])
    ret['dps_bonus_mult'] = float(unit_bonuses['dps_bonus_mult'])
    ret['life_bonus_add'] = float(unit_bonuses['life_bonus_add'])
    ret['life_bonus_mult'] = float(unit_bonuses['life_bonus_mult'])
    ret['wpn_bonus_add'] = float(unit_bonuses['wpn_bonus_add'])
    ret['wpn_bonus_mult'] = float(unit_bonuses['wpn_bonus_mult'])
    ret['wpn_period_mult'] = float(unit_bonuses['wpn_period_mult'])
    ret['sort_with_dps_bonus'] = utils.as_bool(unit_bonuses['sort_with_dps_bonus'])
    ret['sort_with_life_bonus'] = utils.as_bool(unit_bonuses['sort_with_life_bonus'])
    return UnitBonuses(**ret)


def parse_tower_upgrades(tower: Element) -> list[str]:
    upg: list[str] = []
    buttons = tower.findall('CardLayouts/LayoutButtons/Type[@value="AbilCmd"]/..')
    for b in buttons:
        abil_id = xml_helper.get_value(b, sc2_globals.gUnits, 'AbilCmd', '').split(',')[0]
        abil = xml_helper.get_entry(sc2_globals.gAbils, abil_id)
        if abil is None:
            continue
        if abil.tag != 'CAbilTrain':
            continue
        upg.append(xml_helper.get_value(b, sc2_globals.gUnits, 'Face', ''))
    return upg


def parse_tower_upgrades_sylphy(tower: Element) -> list[str]:
    upg: list[str] = []
    buttons = tower.findall('CardLayouts/LayoutButtons/Type[@value="Passive"]/..')
    for button in buttons:
        face = xml_helper.get_value(button, sc2_globals.gUnits, 'Face', '')
        name = get_game_name('Button', face)
        if name is not None and name.startswith('Merge into'):
            upg.append(face)
    return upg


def parse_tower_predecessors(tower: Element) -> list[str]:
    pred: list[str] = []

    while True:
        x_path = f'CUnit/CardLayouts/LayoutButtons/Face[@value="{
            tower.get("id")}"]/../../..[@parent="SquadronUnitTemplate"]'
        potential = sc2_globals.gUnits.findall(x_path)
        if potential:
            if len(potential) == 1:
                if potential[0].get('id', '').endswith('Constructs'):
                    return pred
                # sylphy merged from same towers (add 2 times)
                if potential[0].get('id', '') in ('fNote', 'fApprentice', 'fPatron', 'fTremolo', 'fArtisan', 'fKapelle'):
                    pred.append(potential[0].get('id', ''))
                pred.append(potential[0].get('id', ''))
                tower = potential[0]
            # diverse sylphy
            else:
                pred.extend(x.get('id', '') for x in potential)
                break
        else:
            break
    return pred


def get_unit_cost(entry: Element) -> UnitCost:
    minerals = float(xml_helper.get_value(entry, sc2_globals.gUnits, 'CostResource[Minerals]', '0'))
    vespene = float(xml_helper.get_value(entry, sc2_globals.gUnits, 'CostResource[Vespene]', '0'))
    supply = float(xml_helper.get_value(entry, sc2_globals.gUnits, 'Food', '0'))
    return UnitCost(minerals, vespene, supply)


def get_damage_type(damage: Element) -> str:
    parent = damage.get('parent')
    if parent == 'SiegeDamage':
        return 'Siege'
    if parent == 'PiercingDamage':
        return 'Piercing'
    if parent == 'NormalDamage':
        return 'Normal'
    if parent == 'MagicDamage':
        return 'Magic'
    if parent == 'ChaosDamage':
        return 'Chaos'
    if parent:
        entry = xml_helper.get_entry(sc2_globals.gEffects, parent)
        if entry is not None:
            return get_damage_type(entry)
    logger.warning('%s: invalid damage type: %s', damage.get('id', str(damage)), parent)
    return 'None'


def get_weapon_damage(weapon: Element) -> Damage:
    wpn_id = weapon.get('id', '')
    dmg_id = xml_helper.get_value(weapon, sc2_globals.gWeapons, 'DisplayEffect', wpn_id)
    ret: dict[str, typing.Any] = {}
    if dmg_id is not None:
        dmg = xml_helper.get_entry(sc2_globals.gEffects, dmg_id)
    if not dmg:
        logger.info('Failed to retrieve damage effect from %s', weapon.get('id'))
        return Damage('N/A', 0, 0, 'N/A', 'N/A', 'N/A')
    ret['id'] = dmg_id
    ret['min'] = float(xml_helper.get_value(dmg, sc2_globals.gEffects, 'Amount', '0'))
    # some units use an accumulator directly:
    accum = dmg.find("Amount/AccumulatorArray")
    if ret['min'] <= 0 and accum is not None:
        accum_id = accum.get('value', None)
        if accum_id is not None:
            accum = xml_helper.get_entry(sc2_globals.gAccumulators, accum_id)
            if accum is not None and accum.tag == 'CAccumulatorConstant':
                ret['min'] = float(xml_helper.get_value(accum, sc2_globals.gAccumulators, 'Amount', '0'))

    ret['max'] = float(ret['min']) + \
        float(xml_helper.get_value(dmg, sc2_globals.gEffects, 'Random', '0'))
    ret['kind'] = xml_helper.get_value(dmg, sc2_globals.gEffects, 'Kind', 'Melee')
    ret['dmg_type'] = get_damage_type(dmg)
    ret['effect_type'] = xml_helper.get_value(dmg, sc2_globals.gEffects, 'Type', 'None')
    return Damage(**ret)


def get_unit_weapon(unit: Element) -> Weapon:
    wpn_id = xml_helper.get_value(unit, sc2_globals.gUnits, 'WeaponArray.Link', '')
    if not wpn_id:
        logger.info('%s has no weapon; setting to defaults', unit.get('id'))
        return Weapon('N/A', 'N/A', Damage('N/A', 0, 0, 'N/A', 'N/A', 'N/A'), 1, 0, 0, True)
    ret: dict[str, typing.Any] = {}
    wpn = xml_helper.get_entry(sc2_globals.gWeapons, wpn_id)
    if not wpn:
        logger.info('%s failed to get unit weapon; setting to defaults', unit.get('id'))
        return Weapon('N/A', 'N/A', Damage('N/A', 0, 0, 'N/A', 'N/A', 'N/A'), 1, 0, 0, True)
    ret['id'] = wpn_id
    ret['name'] = get_game_name('Weapon', wpn_id, 'N/A')
    ret['damage'] = get_weapon_damage(wpn)
    ret['period'] = float(xml_helper.get_value(wpn, sc2_globals.gWeapons, 'Period', '0.8332'))
    ret['targets'] = int(xml_helper.get_value(wpn, sc2_globals.gWeapons, 'DisplayAttackCount', '1'))
    ret['range'] = float(xml_helper.get_value(wpn, sc2_globals.gWeapons, 'Range', '5'))
    ret['melee'] = bool(int(xml_helper.get_value(wpn, sc2_globals.gWeapons, 'Options[Melee]', '0')))
    return Weapon(**ret)


def parse_unit_data(entry: Element, bonuses: dict[str, dict[str, str]]) -> Unit:
    ret: dict[str, typing.Any] = {}
    ret['cost'] = get_unit_cost(entry)
    ret['id'] = entry.get('id')
    ret['name'] = get_game_name('Unit', ret['id'])
    ret['hp'] = float(xml_helper.get_value(entry, sc2_globals.gUnits, 'LifeMax', '1'))
    ret['shields'] = float(xml_helper.get_value(entry, sc2_globals.gUnits, 'ShieldsMax', '0'))
    ret['energy'] = float(xml_helper.get_value(entry, sc2_globals.gUnits, 'EnergyMax', '0'))
    # ideally we get all attribute elements, but in squadron all units have just 1 armor type
    ret['armor'] = xml_helper.get_value(entry, sc2_globals.gUnits, 'Attributes', 'None', 'index')
    ret['move_speed'] = float(xml_helper.get_value(entry, sc2_globals.gUnits, 'Speed', '0'))
    ret['wpn'] = get_unit_weapon(entry)
    # keep empty and update later
    ret['abilities'] = []
    ret['bonuses'] = parse_unit_bonuses(ret['name'], bonuses)
    return Unit(**ret)


def parse_tower_data(entry: Element, bonuses: dict[str, dict[str, str]]) -> Tower:
    ret: dict[str, typing.Any] = {}
    u = parse_unit_data(entry, bonuses)
    unit_bonuses = bonuses.get(u.name)
    if unit_bonuses:
        ret['builder'] = unit_bonuses['builder']
        ret['tier'] = unit_bonuses['tier']
    # TODO
    ret['upgrades'] = parse_tower_upgrades_sylphy(entry) if ret['builder'] == 'Sylphy' else parse_tower_upgrades(entry)
    ret['predecessors'] = parse_tower_predecessors(entry)
    return Tower(**u.__dict__, **ret)


def parse_send_data(entry: Element, bonuses: dict[str, dict[str, str]]) -> Send:
    u = parse_unit_data(entry, bonuses)
    ret: dict[str, typing.Any] = {}
    ret['income'] = float(xml_helper.get_value(entry, sc2_globals.gUnits, 'KillResource[Minerals]', '0'))
    ret['bounty'] = float(u.cost.vespene / 20.0)
    return Send(**u.__dict__, **ret)


def parse_wave_data(entry: Element, bonuses: dict[str, dict[str, str]]) -> Wave:
    u = parse_unit_data(entry, bonuses)
    wave_entry = xml_helper.get_entry(sc2_globals.gUserData, 'SquadWaveClassic')
    instance_path = f'Instances/GameLink/GameLink[@value="{u.id}"]/../../Int/Int'
    ret: dict[str, typing.Any] = {}
    ret['count'] = 0
    if wave_entry:
        count = wave_entry.find(instance_path)
        if count is not None:
            ret['count'] = int(count.get('value', '')) * 3
    ret['index'] = int(u.id.lstrip('Wave0'))
    ret['bounty'] = float(xml_helper.get_value(entry, sc2_globals.gUnits, 'KillResource[Minerals]', '0'))
    return Wave(**u.__dict__, **ret)


def update_tower_costs(towers: dict[str, Tower]) -> None:
    for key, info in towers.items():
        # for non sylphy units just add first predecessor, since it already has total cost (in case of >2 levels)
        if not info.builder == 'Sylphy':
            if info.predecessors:
                unit = towers[info.predecessors[0]]
                towers[key].cost.minerals += unit.cost.minerals
                towers[key].cost.vespene += unit.cost.vespene
                towers[key].cost.supply += unit.cost.supply
        else:
            # cost is set on merged unit data, so just update supply
            for p in info.predecessors:
                unit = towers[p]
                towers[key].cost.supply += unit.cost.supply


def parse_tower_abilities(tower: Element) -> list[str]:
    abils = []
    buttons = tower.findall('CardLayouts/LayoutButtons/Type[@value="Passive"]/..')
    for b in buttons:
        button_id = xml_helper.get_value(b, sc2_globals.gUnits, 'Face', '')
        if button_id != '':
            text = get_game_name('Button', button_id)
            if text:
                if text.startswith('Merge into'):
                    continue
                if text.startswith('Soul Type'):
                    continue
            abils.append(button_id)
    return abils


def extract_tower_abilities(tower: Tower) -> dict[str, Ability]:
    abils: dict[str, Ability] = {}
    entry = xml_helper.get_entry(sc2_globals.gUnits, tower.id)
    if entry is None:
        return {}
    abil_list = parse_tower_abilities(entry)
    for abil in abil_list:
        a = {}
        a['name'] = get_game_name('Button', abil, default='')
        a['desc'] = dref.decode_dref_string(get_game_tooltip(abil, default=''))
        if a['name'] == '' or a['desc'] == '':
            continue
        abils[a['name'].lower()] = Ability(**a)
    tower.abilities = list(abils.keys())
    return abils


def update_tower_abils(towers: dict[str, Tower]) -> dict[str, Ability]:
    abils: dict[str, Ability] = {}
    for v in towers.values():
        abils.update(extract_tower_abilities(v))
    return abils


def extract_send_abilities(send: Send) -> dict[str, Ability]:
    abils: dict[str, Ability] = {}
    text_split = []
    text = get_game_tooltip(send.id)
    if text is not None:
        text_split = text.split('<c val="8080C0">', maxsplit=1)
    if len(text_split) < 2:
        return {}
    abil_text = text_split[1]
    abil_text = re.sub(r'<\/?n\/?>', '', abil_text[:4]) + abil_text[4:]
    for abil in dref.decode_dref_string(abil_text).split('\n'):
        split = abil.split(': ', 1)
        a = {}
        a['name'] = split[0]
        a['desc'] = split[1] if len(split) > 1 else ''
        abils[split[0].lower()] = Ability(**a)
    send.abilities = list(abils.keys())
    return abils


def update_send_abils(sends: dict[str, Send]) -> dict[str, Ability]:
    abils: dict[str, Ability] = {}
    for v in sends.values():
        abils.update(extract_send_abilities(v))
    return abils


def extract_wave_abils(wave: Wave) -> dict[str, Ability]:
    abils: dict[str, Ability] = {}
    text = get_game_tooltip(wave.id)
    if text is None or text == '':
        return {}
    text = re.sub(r'<s.*</s>', '', text)
    text = dref.strip_leading_newlines(text)
    if text is None or text == '':
        return {}
    for abil in dref.decode_dref_string(text).split('\n'):
        split = abil.split(': ')
        a = {}
        a['name'] = split[0]
        a['desc'] = split[1] if len(split) > 1 else ''
        abils[split[0].lower()] = Ability(**a)
    wave.abilities = list(abils.keys())
    return abils


def update_wave_abils(waves: dict[str, Wave]) -> dict[str, Ability]:
    abils: dict[str, Ability] = {}
    for v in waves.values():
        abils.update(extract_wave_abils(v))
    return abils


def load_game_data() -> GameData:
    """
    parses all towers, sends and waves that are defined in *_bonuses.csv files
    """
    towers: dict[str, Tower] = {}
    sends: dict[str, Send] = {}
    waves: dict[str, Wave] = {}
    abils: dict[str, Ability] = {}

    tower_bonuses = dict((row['name'], row) for row in csv.DictReader(
        open(sc2_globals.DATA_DIR / 'bonuses/unit_bonuses.csv', encoding='utf-8')))
    send_bonuses = dict((row['name'], row) for row in csv.DictReader(
        open(sc2_globals.DATA_DIR / 'bonuses/send_bonuses.csv', encoding='utf-8')))
    wave_bonuses = dict((row['name'], row) for row in csv.DictReader(
        open(sc2_globals.DATA_DIR / 'bonuses/wave_bonuses.csv', encoding='utf-8')))
    for unit in sc2_globals.gUnits.findall('CUnit'):
        parent_id = unit.get('parent')
        if not parent_id or 'default' in unit.attrib:
            continue
        unit_id = unit.get('id', '')
        name = get_game_name('Unit', unit_id)
        if parent_id == 'SquadronUnitTemplate':
            if name not in tower_bonuses:
                logger.warning('%s not present in bonuses, skipping', name)
                continue
            towers[unit_id] = parse_tower_data(unit, tower_bonuses)
        elif parent_id == 'SendBase':
            if name not in send_bonuses:
                logger.warning('%s not present in bonuses, skipping', name)
                continue
            sends[unit_id] = parse_send_data(unit, send_bonuses)
        elif parent_id == 'WaveCreepBase':
            if name not in wave_bonuses:
                logger.warning('%s not present in bonuses, skipping', name)
                continue
            waves[unit_id] = parse_wave_data(unit, wave_bonuses)
        else:
            pass

    update_tower_costs(towers)
    abils.update(update_tower_abils(towers))
    abils.update(update_send_abils(sends))
    abils.update(update_wave_abils(waves))
    # 1, 2, 1u, 1uu
    # towers = dict(sorted(towers.items(), key=lambda x: (x[1].builder, x[1].tier[::-1])))
    # 1, 1u, 1uu, 2
    towers = dict(sorted(towers.items(), key=lambda x: (x[1].builder, x[1].tier, x[1].cost.minerals, x[1].name)))
    sends = dict(sorted(sends.items(), key=lambda x: x[1].cost.vespene))
    waves = dict(sorted(waves.items(), key=lambda x: x[1].index))
    return GameData(towers, sends, waves, abils)


def parse_version(version: Element, width: int = 2) -> float:
    # 1.5 < 1.15
    version_text = version.text
    if not version_text:
        logger.error("version not found")
        return 0.0
    base, fraction = version_text.split('.')
    number = f'{int(base)}.{int(fraction):0{width}d}'
    return float(number)


def get_version() -> str:
    vers = max(map(parse_version, sc2_globals.gDocInfo.findall('PatchNote/Version/Value')))
    return f'{vers:.2f}'
